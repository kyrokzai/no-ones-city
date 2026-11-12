"""NO ONE'S CITY — Episode 001 / M0.3: cinematic camera for a 15 s Instagram Reels preview.

Works on the existing M0.2 scene (does NOT rebuild the district):
  1. opens scenes/noc_ep001_district.blend
  2. applies a small polish pass (softer windows, livelier foreground, lamp glow)
  3. adds Cam_Cinematic + Cam_Target with a 360-frame (24 fps) camera move
  4. validates the path (clearance to geometry, smooth speed)
  5. optionally saves, renders control frames and a light MP4 preview

Shots (24 fps):
   0-4 s  low glide along the lit house fronts on Front Street
   4-8 s  push in up the avenue towards the plaza / fountain / cherry trees
   8-12 s crane up and arc left, revealing the waterfront, lake and skyline
  12-15 s wide establishing shot of the district at sunset

Usage (bpy module or `blender -b -P animate_camera.py -- ...`):
    python animate_camera.py --blend ../scenes/noc_ep001_district.blend --save ../scenes/noc_ep001_district.blend \
        --control-frames ../renders/m0.3_control --preview-video ../renders/m0.3_preview_540x960_12fps.mp4

Options: --engine CYCLES|EEVEE, --samples N (preview), --control-samples N, --check-only.
"""

import argparse
import math
import os
import sys
import time

import bpy  # must come before bmesh/mathutils users when used as a module
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_district as bd  # noqa: E402  (reuse the generator's helpers)

FPS = 24
FRAMES = 360

# (frame, camera location, look-at target, lens mm)
KEYS = [
    (-23, (31.0, -32.4, 2.0),  (26.0, -20.8, 2.0), 26),   # pre-roll: frame 1 starts already moving
    (1,   (26.0, -32.3, 2.05), (21.0, -20.5, 2.0), 26),
    (48,  (16.0, -32.2, 2.15), (9.0, -19.5, 1.9), 26),
    (96,  (6.0, -31.0, 2.4),   (1.5, -12.0, 1.6), 27),
    (144, (2.8, -24.0, 3.1),   (0.5, -3.0, 0.9), 28),
    (192, (1.2, -18.0, 4.3),   (0.0, 0.0, 0.6), 28),
    (240, (-6.5, -18.5, 12.5), (0.5, 13.0, 2.0), 28),
    (288, (-15.0, -31.0, 26.0), (2.0, 26.0, 2.0), 29),
    (360, (-16.5, -44.0, 31.0), (3.0, 15.0, 4.0), 30),
]
CONTROL_FRAMES = [1, 72, 168, 264, 360]


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    p.add_argument("--blend", default=os.path.join(here, "..", "scenes", "noc_ep001_district.blend"))
    p.add_argument("--save", default="")
    p.add_argument("--control-frames", default="", help="directory for the 5 control frames")
    p.add_argument("--control-samples", type=int, default=48)
    p.add_argument("--preview-video", default="")
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--engine", default="CYCLES", choices=["CYCLES", "EEVEE"])
    p.add_argument("--check-only", action="store_true")
    return p.parse_known_args(argv)[0]


# --------------------------------------------------------------------------- polish pass

def attach_generator_state():
    """Let build_district helpers (mat/coll/box/...) work on the loaded file."""
    bd.MATS.clear()
    bd.MATS.update({m.name: m for m in bpy.data.materials})
    bd.COLLS.clear()
    bd.COLLS.update({c.name: c for c in bpy.data.collections})


def set_emission(name, strength):
    m = bpy.data.materials.get(name)
    if m:
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = strength


def polish():
    scene = bpy.context.scene
    # 1. less blown-out windows (keep them warm) - idempotent, always applied
    set_emission("window", 2.4)
    set_emission("window_soft", 1.6)
    set_emission("lamp", 16.0)
    if scene.get("noc_m03_polish"):
        return
    attach_generator_state()
    M = bd.MATS.__getitem__
    # 2. livelier foreground: a small park strip south of Front Street
    c = bd.coll("Foreground")
    bd.box("Park_Path", (90, 2.4, 0.1), (0, -41.5, 0), M("sidewalk"), c)
    for k, x in enumerate(range(-40, 41, 8)):
        if abs(x) < 6:
            continue
        bd.flowerbed(f"Park_Bed_{k}", (x + 2.0, -38.9, 0), 3.0, 1.1, c)
        bd.shrub(f"Park_Shrub_{k}a", (x - 1.0, -44.0, 0), 0.6, c)
        bd.shrub(f"Park_Shrub_{k}b", (x + 0.2, -44.4, 0), 0.45, c)
        bd.cyl(f"Park_Bollard_{k}", 0.12, 0.12, 0.7, 8, (x - 2.5, -40.1, 0), M("bollard"), c)
        if k % 2:
            bd.box(f"Park_Bench_{k}", (1.8, 0.55, 0.45), (x + 4.0, -43.1, 0.1), M("wood"), c)
    for k, x in enumerate((-30, -10, 10, 30)):
        bd.cherry(f"Park_Cherry_{k}", (x, -46.5, 0), size=1.1, c=c)
    # 3. gentle lamp glow: real light under the unlit cross-street / lake lamp heads (cheap with light tree)
    n = 0
    for ob in list(bpy.data.objects):
        if ob.name.endswith("_head") and (ob.name.startswith("CrossLamp") or ob.name.startswith("LakeLamp")):
            x, y, z = ob.location
            bd.point_light(f"{ob.name}_glow", (x, y, z - 0.3), energy=140, radius=0.4)
            n += 1
    # slightly softer bloom
    nt = scene.node_tree
    g = next((nd for nd in nt.nodes if nd.bl_idname == "CompositorNodeGlare"), None)
    if g:
        g.threshold = 1.0
        g.mix = -0.3
    scene["noc_m03_polish"] = True
    print(f"[NOC] polish pass: windows softened, park strip added, {n} lamp glows")


# --------------------------------------------------------------------------- camera

def build_camera():
    scene = bpy.context.scene
    for name in ("Cam_Cinematic", "Cam_Target"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    target = bpy.data.objects.new("Cam_Target", None)
    target.empty_display_size = 0.5
    scene.collection.objects.link(target)
    cam_data = bpy.data.cameras.new("Cam_Cinematic")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36
    cam_data.clip_start = 0.1
    cam_data.clip_end = 3000
    cam = bpy.data.objects.new("Cam_Cinematic", cam_data)
    scene.collection.objects.link(cam)
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    for f, loc, tgt, lens in KEYS:
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
        target.location = tgt
        target.keyframe_insert("location", frame=f)
        cam_data.lens = lens
        cam_data.keyframe_insert("lens", frame=f)
    for idb in (cam, target, cam_data):
        for fc in idb.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()

    scene.camera = cam
    scene.frame_start, scene.frame_end = 1, FRAMES
    scene.render.fps = FPS
    return cam


# --------------------------------------------------------------------------- validation

def validate(cam):
    """Clearance to geometry along the whole path + speed smoothness."""
    scene = bpy.context.scene
    dirs = [Vector(d).normalized() for d in
            [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
             (1, 1, 0), (1, -1, 0), (-1, 1, 0), (-1, -1, 0), (1, 0, -1), (-1, 0, -1), (0, 1, -1), (0, -1, -1)]]
    min_clear, min_frame, min_ground = 1e9, 0, 1e9
    positions = []
    for f in range(1, FRAMES + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        p = cam.matrix_world.translation.copy()
        positions.append(p)
        for d in dirs:
            hit, loc, *_ = scene.ray_cast(dg, p, d, distance=50)
            if hit:
                dist = (loc - p).length
                if dist < min_clear:
                    min_clear, min_frame = dist, f
                if d.z == -1:
                    min_ground = min(min_ground, dist)
    speeds = [(positions[i + 1] - positions[i]).length * FPS for i in range(len(positions) - 1)]
    accel = [abs(speeds[i + 1] - speeds[i]) * FPS for i in range(len(speeds) - 1)]
    report = {
        "min_clearance_m": round(min_clear, 2), "at_frame": min_frame,
        "min_height_above_surface_m": round(min_ground, 2),
        "speed_m_s": {"min": round(min(speeds), 2), "max": round(max(speeds), 2)},
        "max_accel_m_s2": round(max(accel), 2),
        "path_length_m": round(sum(speeds) / FPS, 1),
    }
    print("[NOC] path check:", report)
    scene.frame_set(1)
    return report


# --------------------------------------------------------------------------- render

def configure_engine(engine, samples):
    s = bpy.context.scene
    if engine == "EEVEE":
        s.render.engine = "BLENDER_EEVEE_NEXT"
        s.eevee.taa_render_samples = samples
    else:
        s.render.engine = "CYCLES"
        s.cycles.samples = samples
        s.cycles.adaptive_threshold = 0.05
        s.cycles.use_denoising = True
        s.render.use_persistent_data = True   # only the camera moves: keep BVH between frames


def render_control_frames(out_dir, engine, samples):
    s = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    configure_engine(engine, samples)
    s.render.resolution_percentage = 50
    s.render.image_settings.file_format = "PNG"
    for f in CONTROL_FRAMES:
        s.frame_set(f)
        s.render.filepath = os.path.join(os.path.abspath(out_dir), f"m0.3_control_f{f:03d}_{(f - 1) / FPS:04.1f}s.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[NOC] control frame {f}: {time.time() - t:.1f}s")


def render_preview(path, engine, samples):
    s = bpy.context.scene
    configure_engine(engine, samples)
    s.render.resolution_percentage = 50          # 540 x 960
    s.frame_start, s.frame_end, s.frame_step = 1, FRAMES, 2
    s.render.fps = 12                            # 180 frames / 12 fps = 15 s, same timing
    s.render.image_settings.file_format = "FFMPEG"
    s.render.ffmpeg.format = "MPEG4"
    s.render.ffmpeg.codec = "H264"
    s.render.ffmpeg.constant_rate_factor = "MEDIUM"
    s.render.ffmpeg.ffmpeg_preset = "GOOD"
    s.render.ffmpeg.audio_codec = "NONE"
    s.render.filepath = os.path.abspath(path)
    t = time.time()
    bpy.ops.render.render(animation=True)
    print(f"[NOC] preview video: {time.time() - t:.0f}s total")
    # restore delivery settings in the saved scene state
    s.frame_step, s.render.fps = 1, FPS
    s.render.image_settings.file_format = "PNG"


def main():
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    attach_generator_state()
    polish()
    cam = build_camera()
    validate(cam)
    if args.save:
        s = bpy.context.scene
        s.render.resolution_percentage = 100
        s.cycles.samples = 96
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save), compress=True)
        print(f"[NOC] saved {os.path.abspath(args.save)}")
    if args.check_only:
        return
    if args.control_frames:
        render_control_frames(args.control_frames, args.engine, args.control_samples)
    if args.preview_video:
        render_preview(args.preview_video, args.engine, args.samples)


if __name__ == "__main__":
    main()
