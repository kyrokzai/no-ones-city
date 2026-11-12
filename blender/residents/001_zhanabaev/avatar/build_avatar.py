"""NO ONE'S CITY — Resident #001 avatar (M0.7): build, studio scene, city integration, checks.

Generic logic lives in blender/avatar_kit/avatar_core.py; this script only feeds it the resident config
(avatar_config.json) and handles files, cameras and placement.

    # 1) standalone model + neutral studio + cameras -> resident_001_avatar.blend (+ studio previews)
    python build_avatar.py --studio --save resident_001_avatar.blend --previews previews

    # 2) add the avatar to the city next to Founder Residence 001 (backs up the city scene first)
    python build_avatar.py --city ../../../episode-001/scenes/noc_ep001_district.blend --previews previews

Blender 4.2+ (`blender -b -P build_avatar.py -- ...`) or the bpy module.
"""

import argparse
import json
import math
import os
import shutil
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "avatar_kit")))
import avatar_core as ac  # noqa: E402

COLLECTION = "RESIDENT_001_AVATAR"
PREFIX = "AV001"

# camera rig relative to the avatar (avatar faces -Y): name -> (offset, target offset, lens)
CAMERAS = {
    "Avatar001_Front": ((0.0, -3.5, 1.0), (0.0, 0.0, 0.92), 50),
    "Avatar001_Left": ((3.5, 0.0, 1.0), (0.0, 0.0, 0.92), 50),            # character's left profile
    "Avatar001_Back": ((0.0, 3.5, 1.0), (0.0, 0.0, 0.92), 50),
    "Avatar001_ThreeQuarter": ((-2.0, -2.8, 1.25), (0.0, 0.0, 0.96), 50),
    "Avatar001_Portrait": ((-0.22, -1.05, 1.6), (0.0, 0.0, 1.53), 60),
    "Avatar001_AtResidence": ((3.1, -7.0, 2.9), (-0.7, 1.8, 1.25), 36),
}


def load_config():
    with open(os.path.join(HERE, "avatar_config.json")) as fh:
        return json.load(fh)


def add_cameras(arm, col, names=None):
    cams = {}
    for name, (off, tgt, lens) in CAMERAS.items():
        if names and name not in names:
            continue
        for old in (name, f"{name}_Target"):
            ob = bpy.data.objects.get(old)
            if ob:
                bpy.data.objects.remove(ob, do_unlink=True)
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = 36
        cd.clip_start = 0.05
        cd.clip_end = 3000
        cam = bpy.data.objects.new(name, cd)
        col.objects.link(cam)
        t = bpy.data.objects.new(f"{name}_Target", None)
        t.empty_display_size = 0.15
        col.objects.link(t)
        R = arm.matrix_world.to_3x3()
        cam.location = arm.location + R @ Vector(off)
        t.location = arm.location + R @ Vector(tgt)
        con = cam.constraints.new("TRACK_TO")
        con.target = t
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        cams[name] = cam
    if not names:   # in the city: soft warm fill on the face for the presentation camera
        old = bpy.data.objects.get("Avatar001_FaceLight")
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ld = bpy.data.lights.get("Avatar001_FaceLight") or bpy.data.lights.new("Avatar001_FaceLight", "AREA")
        ld.energy, ld.size, ld.color = 45, 1.2, (1.0, 0.88, 0.75)
        lo = bpy.data.objects.new("Avatar001_FaceLight", ld)
        col.objects.link(lo)
        R = arm.matrix_world.to_3x3()
        lo.location = arm.location + R @ Vector((1.2, -2.2, 2.4))
        lo.rotation_euler = (arm.location + Vector((0, 0, 1.55)) - lo.location).to_track_quat("-Z", "Y").to_euler()
    return cams


def build_studio():
    """Neutral grey studio: floor + curved backdrop, soft three-point lighting."""
    s = bpy.context.scene
    w = bpy.data.worlds.new("AV_Studio_World")
    s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.045, 0.047, 0.055, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    col = bpy.data.collections.new("STUDIO")
    s.collection.children.link(col)
    m = bpy.data.materials.new("STUDIO_backdrop")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.31, 0.33, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    import bmesh
    bm = bmesh.new()
    rows = []
    for i in range(13):                       # floor sweeping up into a wall (cyclorama)
        a = math.radians(90) * i / 12
        y = 4.5 + 2.5 * math.sin(a) if i else -8.0
        z = 2.5 - 2.5 * math.cos(a) if i else 0.0
        rows.append((y if i else -8.0, z))
    rows.append((7.0, 6.0))
    verts = [[bm.verts.new((x, y, z)) for x in (-8.0, 8.0)] for y, z in rows]
    for a, b in zip(verts, verts[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0]))
    me = bpy.data.meshes.new("STUDIO_cyclorama")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(m)
    ob = bpy.data.objects.new("STUDIO_cyclorama", me)
    col.objects.link(ob)
    for name, loc, energy, size, color in (("STUDIO_Key", (-2.4, -2.8, 3.2), 330, 1.8, (1.0, 0.95, 0.9)),
                                           ("STUDIO_Fill", (2.8, -2.2, 1.8), 160, 2.2, (0.85, 0.9, 1.0)),
                                           ("STUDIO_Rim", (1.2, 2.6, 3.0), 380, 1.0, (0.95, 0.85, 1.0))):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        col.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    s.render.engine = "CYCLES"
    s.view_settings.view_transform = "AgX"
    s.render.resolution_x, s.render.resolution_y = 1080, 1920
    s.cycles.use_denoising = True


def render(cams, out_dir, samples, names, tag=""):
    s = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    s.render.engine = "CYCLES"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.render.resolution_percentage = 50
    s.render.image_settings.file_format = "PNG"
    keep = s.camera
    for n in names:
        s.camera = cams[n]
        s.render.filepath = os.path.join(os.path.abspath(out_dir), f"{n}{tag}.png")
        bpy.ops.render.render(write_still=True)
        print("[AV001] rendered", n + tag)
    s.camera = keep


def missing_images():
    out = []
    for im in bpy.data.images:
        if im.source == "FILE" and not im.packed_file and not os.path.exists(bpy.path.abspath(im.filepath)):
            out.append(im.name)
    return out


def world_bbox(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = ob.evaluated_get(dg)
    cs = [eo.matrix_world @ Vector(c) for c in eo.bound_box]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))


def validate_city(arm, B, before):
    """Placement in the city: on the ground, no clashes, city / residence / cameras intact."""
    rep = {}
    s = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    av = set(o.name for o in B.parts.values())
    # ground under the feet (ray down, ignoring the avatar)
    feet_z = min(world_bbox(B.parts[f"sole_{k}"])[0].z for k in ("L", "R"))
    ground = []
    for k in ("L", "R"):
        c = sum(world_bbox(B.parts[f"sole_{k}"]), Vector()) / 2
        o = Vector((c.x, c.y, feet_z + 0.5))
        hit, loc, _n, _i, ob, _m = s.ray_cast(dg, o, Vector((0, 0, -1)), distance=2.0)
        while hit and ob.name in av:
            o = loc + Vector((0, 0, -1e-4))
            hit, loc, _n, _i, ob, _m = s.ray_cast(dg, o, Vector((0, 0, -1)), distance=2.0)
        ground.append((round(loc.z, 4) if hit else None, ob.name if hit else None))
    rep["feet_min_z"] = round(feet_z, 4)
    rep["ground_under_feet"] = ground
    rep["feet_gap_mm"] = [round((feet_z - g[0]) * 1000, 1) for g in ground if g[0] is not None]
    # clashes with any city / residence object (AABB, 5 mm tolerance)
    clashes = []
    av_bb = [(o.name, world_bbox(o)) for o in B.parts.values()]
    for ob in bpy.data.objects:
        if ob.type not in ("MESH", "FONT") or ob.name in av or ob.name in ("Ground", "Lake"):
            continue
        bb = world_bbox(ob)
        if (bb[1] - bb[0]).x > 150:
            continue
        for n, a in av_bb:
            if all(a[0][i] < bb[1][i] - 0.005 and bb[0][i] < a[1][i] - 0.005 for i in range(3)):
                clashes.append(f"{n} x {ob.name}")
    rep["clashes"] = clashes
    sign = bpy.data.objects.get("RES001_SignText1") or next((o for o in bpy.data.objects if o.name.startswith("RES001_") and "Sign_Monolith" in o.name), None)
    if sign:
        rep["distance_to_sign_m"] = round((world_bbox(sign)[0] + world_bbox(sign)[1]).__truediv__(2).xy.__sub__(arm.location.xy).length, 2)
    door = next((o for o in bpy.data.objects if o.name.startswith("RES001_") and o.name.endswith("_Door")), None)
    if door:
        rep["door_height_m"] = round(world_bbox(door)[1].z - world_bbox(door)[0].z, 2)
    # city integrity
    after = {o.name for o in bpy.data.objects}
    rep["objects_removed_from_city"] = sorted(before - after)[:10]
    res = bpy.data.collections.get("RESIDENT_001_FOUNDER_RESIDENCE")
    rep["residence_objects"] = len(res.all_objects) if res else 0
    rep["cameras_present"] = {n: bool(bpy.data.objects.get(n)) for n in
                              ("Cam_Cinematic", "Cam_Reels", "Resident001_Front", "Resident001_Waterfront", "Resident001_Left",
                               "Resident001_Right", "Resident001_Aerial", "Resident001_Sign", "Resident001_Orbit")}
    # face visible from the presentation camera (ray to the nose tip)
    cam = bpy.data.objects["Avatar001_AtResidence"]
    tip = sum(world_bbox(B.parts["nose_tip"]), Vector()) / 2
    o = cam.matrix_world.translation
    d = tip - o
    hit, loc, _n, _i, ob, _m = s.ray_cast(dg, o, d.normalized(), distance=d.length + 0.05)
    rep["face_visible_from_AtResidence"] = bool(hit and ob.name in av)
    return rep


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--studio", action="store_true")
    p.add_argument("--city", default="")
    p.add_argument("--save", default="")
    p.add_argument("--previews", default="")
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--report", default="")
    return p.parse_known_args(argv)[0]


def main():
    args = parse_args()
    cfg = load_config()
    reports = {}
    if args.studio:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        build_studio()
        arm, B, full = ac.build_avatar(cfg, COLLECTION, PREFIX)
        ac.place(arm, (0, 0, 0))
        rep = ac.validate_avatar(arm, B)
        rep["missing_images"] = missing_images()
        reports["model"] = rep
        for k, v in rep.items():
            print(f"[AV001] {k}: {v}")
        ac.apply_pose(arm, full["placement"]["pose"])
        cams = add_cameras(arm, bpy.data.collections[COLLECTION],
                           [n for n in CAMERAS if n != "Avatar001_AtResidence"])
        bpy.context.scene.camera = cams["Avatar001_ThreeQuarter"]
        if args.save:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, args.save) if not os.path.isabs(args.save) else args.save, compress=True)
            print("[AV001] saved", args.save)
        if args.previews:
            out = os.path.join(HERE, args.previews)
            render(cams, out, args.samples, ["Avatar001_Front", "Avatar001_Left", "Avatar001_Back", "Avatar001_ThreeQuarter", "Avatar001_Portrait"])
            ac.apply_pose(arm, "test_arms")
            render(cams, out, max(8, args.samples // 2), ["Avatar001_ThreeQuarter"], tag="_test_pose_arms")
            ac.apply_pose(arm, "test_head_legs")
            render(cams, out, max(8, args.samples // 2), ["Avatar001_ThreeQuarter"], tag="_test_pose_head_legs")
            ac.apply_pose(arm, full["placement"]["pose"])
    if args.city:
        city = os.path.abspath(args.city)
        backup = city.replace(".blend", "_m0.6_backup.blend")
        if not os.path.exists(backup):
            shutil.copy2(city, backup)
            print("[AV001] backup", backup)
        bpy.ops.wm.open_mainfile(filepath=city)
        before = {o.name for o in bpy.data.objects}
        arm, B, full = ac.build_avatar(cfg, COLLECTION, PREFIX)
        pl = full["placement"]
        anchor = bpy.data.objects[pl["anchor"]]
        world = anchor.matrix_world @ Vector(pl["local_offset"])
        ac.place(arm, world, math.degrees(anchor.matrix_world.to_euler().z) + pl["rotation_z_deg"])
        ac.apply_pose(arm, pl["pose"])
        cams = add_cameras(arm, bpy.data.collections[COLLECTION])
        rep = validate_city(arm, B, before)
        rep["avatar_world_location"] = [round(v, 2) for v in arm.location]
        rep["missing_images"] = missing_images()
        reports["city"] = rep
        for k, v in rep.items():
            print(f"[AV001] {k}: {v}")
        bpy.ops.wm.save_as_mainfile(filepath=city, compress=True)
        print("[AV001] saved city", city)
        if args.previews:
            render(cams, os.path.join(HERE, args.previews), args.samples, ["Avatar001_AtResidence"])
    if args.report:
        path = os.path.join(HERE, args.report) if not os.path.isabs(args.report) else args.report
        old = {}
        if os.path.exists(path):
            with open(path) as fh:
                old = json.load(fh)
        old.update({k: v for k, v in reports.items()})
        with open(path, "w") as fh:
            json.dump(old, fh, indent=1, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
