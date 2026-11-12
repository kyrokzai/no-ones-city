"""NO ONE'S CITY — Episode 001 / M0.4: cinematic camera (polished) for a 15 s Instagram Reels preview.

Works on the existing M0.2 scene (does NOT rebuild the district):
  1. opens scenes/noc_ep001_district.blend
  2. applies a small polish pass (softer windows, livelier foreground, lamp glow)
  3. adds Cam_Cinematic + Cam_Target with a 360-frame (24 fps) camera move
  4. validates the path (clearance to geometry, smooth speed)
  5. optionally saves, renders control frames and a light MP4 preview

Shots (24 fps):
   0-3 s  elevated glide down Cross Street: lit modern house fronts on both sides, plaza ahead
   3-7 s  smooth push in along the street to the plaza and fountain
   7-11 s crane up over the roofs (above the open street / free plot), revealing the waterfront
  11-15 s wide sunset view: district, fountain, lake, skyline and sun, clean sky band for the logo

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
    (-23, (48.0, -8.0, 10.4),  (18.0, -3.5, 0.4), 28),   # pre-roll: frame 1 starts already moving
    (1,   (44.0, -7.0, 9.8),   (14.0, -3.0, 0.4), 28),
    (72,  (32.0, -4.5, 7.0),   (6.0, 0.0, 0.9), 28),
    (120, (22.0, -3.0, 5.0),   (3.0, 0.0, 1.6), 28),
    (168, (14.0, -3.2, 5.4),   (0.0, 1.5, 1.4), 28),
    (216, (13.2, -10.0, 12.5), (0.0, 6.0, 1.5), 28),
    (264, (12.0, -24.0, 22.0), (0.0, 40.0, 7.0), 27),
    (360, (-4.0, -46.0, 32.0), (2.0, 30.0, 10.0), 26),
]
CONTROL_FRAMES = [1, 48, 96, 144, 192, 240, 288, 360]  # 0, 2, 4, 6, 8, 10, 12, 15 s

# screen-space thresholds for the analysis
GRID_X, GRID_Y = 18, 32
NEAR_WALL_M = 10.0        # a vertical surface closer than this counts as a "near wall"
MAX_NEAR_WALL = 0.08      # share of the frame
NEAR_OBJECT_M = 8.0       # any non-ground object closer than this ...
MAX_NEAR_OBJECT = 0.035   # ... may cover at most this share (plaza furniture on the approach is fine; lamp heads / crowns are not)
MAX_SINGLE_BUILDING = 0.22
MAX_SKY = 0.55
MAX_ASPHALT = 0.40
MAX_TURN_DEG_S = 30.0
KEY_POINTS = {            # name -> world point
    "fountain": (0.0, 0.0, 2.6),
    "plaza_ring": (0.0, -6.7, 0.35),
    "waterfront": (0.0, 40.5, 0.4),
    "lake": (30.0, 120.0, -0.85),
    "skyline": (60.0, 310.0, 30.0),
    "sun": (190.0, 900.0, 88.0),
}
# which key points must be visible (in frame and unoccluded) in which time window (seconds)
REQUIRED = [
    ((0.0, 3.0), ["fountain"]),
    ((3.0, 7.0), ["fountain"]),
    ((7.0, 11.0), ["fountain"]),
    ((10.5, 15.0), ["waterfront"]),
    ((11.0, 15.0), ["lake", "skyline"]),
    ((13.0, 15.0), ["fountain", "sun"]),
]


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    p.add_argument("--blend", default=os.path.join(here, "..", "scenes", "noc_ep001_district.blend"))
    p.add_argument("--save", default="")
    p.add_argument("--control-frames", default="", help="directory for the 5 control frames")
    p.add_argument("--control-samples", type=int, default=32)
    p.add_argument("--preview-video", default="")
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--engine", default="CYCLES", choices=["CYCLES", "EEVEE"])
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--report", default="", help="write the trajectory / composition report (JSON)")
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
    # M0.4: the south-east plaza lamp stood right on the camera's approach line to the fountain;
    # move it ~30 deg further round the plaza ring (absolute position -> idempotent)
    a = -1.0
    for suffix in ("_pole", "_head", "_cap", "_light"):
        ob = bpy.data.objects.get("PlazaLamp_3" + suffix)
        if ob:
            ob.location.x, ob.location.y = math.cos(a) * 9.9, math.sin(a) * 9.9
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

def _category(ob):
    if ob is None:
        return "sky"
    names = {c.name for c in ob.users_collection}
    if "Background" in names:
        return "sky"            # skyline / ridges / sun read as the backdrop
    if "Roads" in names:
        return "asphalt" if ob.name.split("_")[0] in ("Avenue", "CrossSt", "FrontSt", "LakeSt", "WestSt", "EastSt", "Junction") \
            and "walk" not in ob.name else "street"
    if ob.name == "Lake":
        return "water"
    if "Houses" in names:
        return "house"
    return "other"


def _house_root(ob):
    while ob.parent is not None:
        ob = ob.parent
    return ob.name


def analyse_frame(scene, cam, dg):
    """Cast a GRID_X x GRID_Y grid of rays through the camera frustum and classify what fills the frame."""
    from bpy_extras.object_utils import world_to_camera_view
    mw = cam.matrix_world
    origin = mw.translation.copy()
    frame = cam.data.view_frame(scene=scene)        # 4 corners in camera space (z = -d)
    tr, br, bl, tl = frame
    counts = {"sky": 0, "asphalt": 0, "street": 0, "water": 0, "house": 0, "other": 0}
    near_wall = 0
    near_any = 0
    per_building = {}
    n = GRID_X * GRID_Y
    for iy in range(GRID_Y):
        v = (iy + 0.5) / GRID_Y
        left = tl.lerp(bl, v)
        right = tr.lerp(br, v)
        for ix in range(GRID_X):
            u = (ix + 0.5) / GRID_X
            d = (mw.to_3x3() @ left.lerp(right, u)).normalized()
            hit, loc, nrm, _i, ob, _m = scene.ray_cast(dg, origin, d, distance=2000)
            cat = _category(ob if hit else None)
            counts[cat] += 1
            if hit:
                dist = (loc - origin).length
                if dist < NEAR_WALL_M and abs(nrm.z) < 0.5:
                    near_wall += 1
                if dist < NEAR_OBJECT_M and nrm.z < 0.7 and cat not in ("asphalt", "street", "water"):
                    near_any += 1
                if cat == "house":
                    r = _house_root(ob)
                    per_building[r] = per_building.get(r, 0) + 1
    share = {k: v / n for k, v in counts.items()}
    biggest = max(per_building.items(), key=lambda kv: kv[1]) if per_building else ("-", 0)
    # bright lamp heads must not fly through the frame up close
    close_lamps = []
    for ob in LAMP_HEADS:
        p = ob.matrix_world.translation
        dist = (p - origin).length
        if dist < 10.0:
            c = world_to_camera_view(scene, cam, p)
            if -0.05 < c.x < 1.05 and -0.05 < c.y < 1.05 and c.z > 0:
                close_lamps.append(f"{ob.name}@{dist:.1f}m")
    # key point visibility
    vis = {}
    for name, pt in KEY_POINTS.items():
        p = Vector(pt)
        c = world_to_camera_view(scene, cam, p)
        inside = 0.03 < c.x < 0.97 and 0.03 < c.y < 0.97 and c.z > 0
        visible = False
        if inside:
            d = p - origin
            dist = d.length
            hit, loc, *_ = scene.ray_cast(dg, origin, d.normalized(), distance=dist)
            visible = (not hit) or (loc - origin).length > dist - 1.5
            if name in ("skyline", "sun") and hit:       # far targets: a hit on the backdrop counts as visible
                visible = visible or (loc - origin).length > 250
        vis[name] = visible
    return {
        "share": share, "near_wall": near_wall / n, "near_object": near_any / n, "close_lamps": close_lamps,
        "biggest_building": (biggest[0], biggest[1] / n), "visible": vis,
        "forward": (mw.to_3x3() @ Vector((0, 0, -1))).normalized(), "pos": origin,
    }


LAMP_HEADS = []


def validate(cam, step=2):
    """Physical clearance + screen-space composition checks along the whole move."""
    scene = bpy.context.scene
    LAMP_HEADS[:] = [o for o in bpy.data.objects if "Lamp" in o.name and o.name.endswith("_head")]
    dirs = [Vector(d).normalized() for d in
            [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
             (1, 1, 0), (1, -1, 0), (-1, 1, 0), (-1, -1, 0), (1, 0, -1), (-1, 0, -1), (0, 1, -1), (0, -1, -1)]]
    min_clear, min_frame = 1e9, 0
    frames = []
    for f in range(1, FRAMES + 1, step):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        p = cam.matrix_world.translation.copy()
        for d in dirs:
            hit, loc, *_ = scene.ray_cast(dg, p, d, distance=50)
            if hit and (loc - p).length < min_clear:
                min_clear, min_frame = (loc - p).length, f
        a = analyse_frame(scene, cam, dg)
        a["frame"] = f
        frames.append(a)
    if frames[-1]["frame"] != FRAMES:
        scene.frame_set(FRAMES)
        a = analyse_frame(scene, cam, bpy.context.evaluated_depsgraph_get())
        a["frame"] = FRAMES
        frames.append(a)
    issues = []
    for a, b in zip(frames, frames[1:]):
        dt = (b["frame"] - a["frame"]) / FPS
        b["speed"] = (b["pos"] - a["pos"]).length / dt
        b["turn"] = math.degrees(a["forward"].angle(b["forward"])) / dt
    frames[0]["speed"], frames[0]["turn"] = frames[1]["speed"], frames[1]["turn"]
    for a in frames:
        t = (a["frame"] - 1) / FPS
        s = a["share"]
        if a["near_wall"] > MAX_NEAR_WALL:
            issues.append(f"f{a['frame']} near wall covers {a['near_wall']:.0%}")
        if a["close_lamps"]:
            issues.append(f"f{a['frame']} lamp head in frame up close: {', '.join(a['close_lamps'])}")
        if a["near_object"] > MAX_NEAR_OBJECT:
            issues.append(f"f{a['frame']} near object covers {a['near_object']:.1%}")
        if a["biggest_building"][1] > MAX_SINGLE_BUILDING:
            issues.append(f"f{a['frame']} {a['biggest_building'][0]} covers {a['biggest_building'][1]:.0%}")
        if s["sky"] > MAX_SKY:
            issues.append(f"f{a['frame']} sky {s['sky']:.0%}")
        if s["asphalt"] > MAX_ASPHALT:
            issues.append(f"f{a['frame']} asphalt {s['asphalt']:.0%}")
        if a["turn"] > MAX_TURN_DEG_S:
            issues.append(f"f{a['frame']} turn {a['turn']:.0f} deg/s")
        for (t0, t1), names in REQUIRED:
            if t0 <= t <= t1:
                for nm in names:
                    if not a["visible"][nm]:
                        issues.append(f"f{a['frame']} {nm} not visible")
    speeds = [a["speed"] for a in frames]
    accel = [abs(b["speed"] - a["speed"]) / ((b["frame"] - a["frame"]) / FPS) for a, b in zip(frames, frames[1:])]
    summary = {
        "frames_checked": len(frames),
        "min_clearance_m": round(min_clear, 2), "min_clearance_frame": min_frame,
        "speed_m_s": [round(min(speeds), 2), round(max(speeds), 2)],
        "max_accel_m_s2": round(max(accel), 2),
        "max_accel_frame": frames[accel.index(max(accel)) + 1]["frame"],
        "max_turn_deg_s": round(max(a["turn"] for a in frames), 1),
        "max_near_wall_share": round(max(a["near_wall"] for a in frames), 3),
        "max_near_object_share": round(max(a["near_object"] for a in frames), 3),
        "max_single_building_share": round(max(a["biggest_building"][1] for a in frames), 3),
        "max_sky_share": round(max(a["share"]["sky"] for a in frames), 3),
        "max_asphalt_share": round(max(a["share"]["asphalt"] for a in frames), 3),
        "issues": issues,
    }
    per_second = []
    for a in frames:
        if (a["frame"] - 1) % FPS == 0 or a["frame"] == FRAMES:
            per_second.append({
                "t": round((a["frame"] - 1) / FPS, 1), "frame": a["frame"],
                "speed": round(a["speed"], 1), "turn": round(a["turn"], 1),
                "sky": round(a["share"]["sky"], 2), "asphalt": round(a["share"]["asphalt"], 2),
                "houses": round(a["share"]["house"], 2), "water": round(a["share"]["water"], 2),
                "near_wall": round(a["near_wall"], 3), "near_object": round(a["near_object"], 3), "biggest_building": round(a["biggest_building"][1], 2),
                "visible": [k for k, v in a["visible"].items() if v],
            })
    print("[NOC] path check:", {k: v for k, v in summary.items() if k != "issues"})
    print(f"[NOC] issues ({len(issues)}):", issues[:25])
    for row in per_second:
        print("   ", row)
    scene.frame_set(1)
    return {"summary": summary, "per_second": per_second}


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
        s.render.filepath = os.path.join(os.path.abspath(out_dir), f"m0.4_control_f{f:03d}_{(f - 1) / FPS:04.1f}s.png")
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
    report = validate(cam)
    if args.report:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
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
