"""NO ONE'S CITY — Episode 001 / M0.2: first low-poly district (visual polish).

Builds a small modern district procedurally (12 houses, 4 free plots, roads,
sidewalks, central plaza with fountain, trees, street lamps, lake, skyline)
with sunset lighting (navy / gold / soft pink) and a vertical 9:16 camera.

Style: Modern Low-Poly x Cozy Cinematic x Sunset City.
No medieval / fantasy / photoreal buildings.

Run with Blender 4.x (the scene is rebuilt from scratch; the current file is cleared):

    blender -b -P build_district.py -- --save ../scenes/noc_ep001_district.blend \
        --render ../renders/test_frame_1080x1920.png --samples 96

or with the `bpy` Python module (pip install bpy==4.2.0, Python 3.11):

    python build_district.py --save ... --render ...

Options: --save PATH, --render PATH, --samples N, --preview (half resolution),
--seed N. Paths are relative to the current working directory.
"""

import argparse
import math
import os
import random
import sys

import bpy  # must come before bmesh when used as a Python module
import bmesh
from mathutils import Vector

# --------------------------------------------------------------------------- args

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--save", default="")
    p.add_argument("--render", default="")
    p.add_argument("--samples", type=int, default=96)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--seed", type=int, default=1)
    return p.parse_known_args(argv)[0]


# --------------------------------------------------------------------------- helpers

def srgb(hex_str):
    """'#rrggbb' (sRGB) -> linear RGB tuple."""
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


MATS = {}


def mat(name, color, rough=0.7, emit=None, strength=0.0, metallic=0.0, spec=0.5):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb(color), 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*srgb(emit), 1.0)
        b.inputs["Emission Strength"].default_value = strength
    MATS[name] = m
    return m


COLLS = {}


def coll(name):
    if name not in COLLS:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLLS[name] = c
    return COLLS[name]


def mesh_obj(name, bm, material, collection, loc=(0, 0, 0), rot_z=0.0, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = False  # flat shading = low-poly look
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler.z = rot_z
    if parent:
        ob.parent = parent
    return ob


def box(name, size, loc, material, collection, rot_z=0.0, parent=None):
    """Box with its pivot at the bottom centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, 0, size[2] / 2)), verts=bm.verts)
    return mesh_obj(name, bm, material, collection, loc, rot_z, parent)


def cyl(name, r1, r2, h, segs, loc, material, collection, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                          radius1=r1, radius2=r2, depth=h)
    bmesh.ops.translate(bm, vec=Vector((0, 0, h / 2)), verts=bm.verts)
    return mesh_obj(name, bm, material, collection, loc, 0.0, parent)


def blob(name, r, loc, material, collection, scale=(1, 1, 1), jitter=0.12, parent=None):
    """Faceted low-poly crown (jittered icosphere)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0] * (1 + random.uniform(-jitter, jitter))
        v.co.y *= scale[1] * (1 + random.uniform(-jitter, jitter))
        v.co.z *= scale[2] * (1 + random.uniform(-jitter, jitter))
    return mesh_obj(name, bm, material, collection, loc, random.uniform(0, 6.28), parent)


# --------------------------------------------------------------------------- palette

def build_materials():
    mat("grass", "#4f6a34", 0.9)
    mat("grass_lawn", "#5d7a35", 0.85)
    mat("asphalt", "#383e4f", 0.75)
    mat("asphalt_x", "#41475a", 0.72)
    mat("curb", "#d9cdb8", 0.7)
    mat("marking", "#e8c37a", 0.6)
    mat("sidewalk", "#b9a58c", 0.75)
    mat("plaza", "#d8c3a2", 0.65)
    mat("plaza_dark", "#8a7660", 0.7)
    mat("paving_ring", "#c2a582", 0.7)
    mat("bollard", "#ffd9a0", 0.3, emit="#ffbf6a", strength=10.0)
    mat("deck", "#8f5e3d", 0.7)
    mat("rail_glow", "#ffcf80", 0.3, emit="#ffb85c", strength=8.0)
    mat("gold_glow", "#f5b04a", 0.4, emit="#ffb347", strength=6.0)
    mat("water", "#14284a", 0.03, spec=0.9)
    mat("fountain_water", "#6fb6e6", 0.05, emit="#7cc8ff", strength=1.5)
    mat("trunk", "#5a3d2b", 0.9)
    for i, c in enumerate(["#4d7a32", "#5f8c3a", "#3f6b30", "#6e9640"]):
        mat(f"leaf_{i}", c, 0.85)
    mat("leaf_pink", "#e89ab4", 0.8)
    mat("blossom", "#f59ac0", 0.8)
    mat("blossom_light", "#ffc4da", 0.8)
    mat("shrub", "#4f7d3a", 0.9)
    mat("shrub_dark", "#36602f", 0.9)
    mat("soil", "#4a3426", 0.95)
    for n, c in (("pink", "#ff7fae"), ("yellow", "#ffd25a"), ("white", "#fff3e6"), ("coral", "#ff8a62"), ("violet", "#b48cff")):
        mat(f"flower_{n}", c, 0.7)
    mat("leaf_gold", "#d9a441", 0.8)
    mat("hedge", "#3c6630", 0.9)
    for n, c in (("white", "#f4f0e8"), ("sand", "#dcc6a2"), ("grey", "#c3c6ca"),
                 ("blush", "#e9cfc3"), ("cream", "#efe4cf")):
        mat(f"wall_{n}", c, 0.7)
    mat("clad_dark", "#3a3d47", 0.6)
    mat("clad_wood", "#a8714a", 0.55)
    mat("roof_metal", "#4b4f5a", 0.45, metallic=0.3)
    mat("mullion", "#23252c", 0.5)
    mat("wood", "#9a6440", 0.6)
    mat("charcoal", "#2c2f38", 0.6)
    mat("roof", "#3a3d47", 0.7)
    mat("window", "#ffb860", 0.2, emit="#ffa94d", strength=5.5)
    mat("window_soft", "#ffd6a0", 0.2, emit="#ffc98a", strength=3.0)
    mat("window_cool", "#bcd6ff", 0.15, emit="#9ec3ff", strength=1.2)
    mat("glass", "#86a6c4", 0.08, spec=0.9)
    mat("concrete", "#a39c92", 0.8)
    mat("dirt", "#8a6a48", 0.95)
    mat("lamp", "#ffd9a0", 0.3, emit="#ffc977", strength=20.0)
    mat("mountain_far", "#b07a9a", 0.95)
    mat("mountain_near", "#6e4f7e", 0.95)
    mat("sun_disc", "#ff9426", 0.5, emit="#ff7f1a", strength=2.2)
    # skyline material: navy glass with a lit window grid
    m = bpy.data.materials.new("tower_lit")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb("#1a2238"), 1)
    b.inputs["Roughness"].default_value = 0.35
    tc = nt.nodes.new("ShaderNodeTexCoord")
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Color1"].default_value = (*srgb("#ffb860"), 1)
    brick.inputs["Color2"].default_value = (*srgb("#1a2440"), 1)
    brick.inputs["Mortar"].default_value = (0.004, 0.006, 0.014, 1)
    brick.inputs["Scale"].default_value = 0.6
    brick.inputs["Mortar Size"].default_value = 0.35
    brick.inputs["Brick Width"].default_value = 1.0
    brick.inputs["Row Height"].default_value = 0.8
    brick.offset = 0.0
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    add = nt.nodes.new("ShaderNodeMath")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    nt.links.new(add.outputs["Value"], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.9
    MATS["tower_lit"] = m


M = MATS.__getitem__


# --------------------------------------------------------------------------- world & light

def build_world():
    w = bpy.data.worlds.new("NOC_Sunset")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    # gold horizon -> coral -> soft pink -> violet -> deep navy zenith
    stops = [(0.0, "#ffad48"), (0.02, "#ff9450"), (0.045, "#f2807f"), (0.075, "#d06c9c"),
             (0.11, "#7a4a98"), (0.16, "#323a86"), (0.24, "#18225e"), (0.5, "#0b1340"), (1.0, "#050a22")]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], (*srgb(stops[0][1]), 1)
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*srgb(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = (*srgb(col), 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.35
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


SUN_POS = Vector((190, 900, 88))


def build_lights():
    c = coll("Lights")
    sun = bpy.data.lights.new("Sun_Golden", "SUN")
    sun.color = srgb("#ffa24a")
    sun.energy = 7.0
    sun.angle = math.radians(3)
    ob = bpy.data.objects.new("Sun_Golden", sun)
    c.objects.link(ob)
    d = (Vector((0, 0, 0)) - SUN_POS).normalized()
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # cool rim / fill from the opposite side (navy sky bounce)
    fill = bpy.data.lights.new("Fill_Navy", "SUN")
    fill.color = srgb("#6f86d6")
    fill.energy = 0.5
    fill.angle = math.radians(20)
    ob = bpy.data.objects.new("Fill_Navy", fill)
    c.objects.link(ob)
    ob.rotation_euler = Vector((0.3, -1, -0.8)).normalized().to_track_quat("-Z", "Y").to_euler()
    # visible sun disc on the horizon
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=30)
    disc = mesh_obj("Sun_Disc", bm, M("sun_disc"), coll("Background"), SUN_POS)
    disc.rotation_euler = (math.radians(90), 0, 0)
    disc.visible_shadow = False


def point_light(name, loc, color="#ffb866", energy=150, radius=0.3):
    l = bpy.data.lights.new(name, "POINT")
    l.color = srgb(color)
    l.energy = energy
    l.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, l)
    coll("Lights").objects.link(ob)
    ob.location = loc


# --------------------------------------------------------------------------- city pieces

ROAD_Z = 0.02
WALK_H = 0.18


def build_ground_and_water():
    c = coll("Ground")
    box("Ground", (700, 360, 0.1), (0, -140, -0.1), M("grass"), c)
    # lawn fill for the four residential blocks (lower than sidewalks: no coplanar faces)
    for sx in (-1, 1):
        for sy in (-1, 1):
            y0, y1 = (5.7, 25.8) if sy > 0 else (-24.3, -5.7)
            box(f"BlockLawn_{sx}_{sy}", (22.1, y1 - y0, WALK_H - 0.04),
                (sx * 17.25, (y0 + y1) / 2, 0), M("grass_lawn"), c)
    # lake
    box("Lake", (1200, 1200, 0.05), (0, 640, -0.9), M("water"), c)
    build_waterfront()


def build_waterfront():
    """Stone promenade + wooden boardwalk, glowing railing, planters, benches and a pier."""
    c = coll("Waterfront")
    box("Promenade", (700, 2.6, WALK_H), (0, 37.5, 0), M("sidewalk"), c)          # y 36.2..38.8
    box("Boardwalk", (700, 3.4, WALK_H + 0.04), (0, 40.5, 0), M("deck"), c)       # y 38.8..42.2
    box("Quay_Wall", (700, 0.8, 1.15), (0, 42.6, -0.95), M("concrete"), c)
    box("Quay_Step", (700, 1.2, 0.5), (0, 43.4, -0.95), M("concrete"), c)
    # railing: posts with warm caps + top rail
    box("Rail_Top", (220, 0.1, 0.08), (0, 42.0, 1.1), M("charcoal"), c)
    for i, x in enumerate(range(-108, 109, 3)):
        box(f"Rail_Post_{i}", (0.1, 0.1, 0.9), (x, 42.0, WALK_H + 0.04), M("charcoal"), c)
        if i % 2 == 0:
            box(f"Rail_Cap_{i}", (0.16, 0.16, 0.1), (x, 42.0, 1.18), M("rail_glow"), c)
    # planters with cherry trees and benches facing the lake
    for i, x in enumerate(range(-45, 46, 10)):
        if abs(x) < 6:
            continue
        box(f"Planter_{i}", (2.6, 1.4, 0.55), (x, 37.4, WALK_H), M("concrete"), c)
        box(f"Planter_{i}_soil", (2.4, 1.2, 0.05), (x, 37.4, WALK_H + 0.52), M("soil"), c)
        cherry(f"Prom_Cherry_{i}", (x, 37.4, WALK_H + 0.55), size=0.85)
        for k in range(3):
            shrub(f"Planter_{i}_sh{k}", (x - 0.8 + k * 0.8, 36.9, WALK_H + 0.55), 0.35)
        box(f"Prom_Bench_{i}", (1.8, 0.55, 0.45), (x + 4.5, 40.0, WALK_H + 0.04), M("wood"), c)
    # pier with a modern flat-roof pavilion
    px = -9
    box("Pier", (5, 22, 0.35), (px, 53, -0.2), M("deck"), c)
    for k in range(6):
        for sx in (-1, 1):
            cyl(f"Pier_Pile_{k}_{sx}", 0.18, 0.18, 1.2, 6, (px + sx * 2.2, 44 + k * 4, -1.0), M("charcoal"), c)
    for k in range(5):
        box(f"Pier_Light_{k}", (0.2, 0.2, 0.5), (px + 2.3, 45 + k * 4.5, 0.15), M("bollard"), c)
        box(f"Pier_LightL_{k}", (0.2, 0.2, 0.5), (px - 2.3, 45 + k * 4.5, 0.15), M("bollard"), c)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"Pavilion_Post_{sx}_{sy}", (0.18, 0.18, 2.8), (px + sx * 2.0, 60 + sy * 2.0, 0.15), M("charcoal"), c)
    box("Pavilion_Roof", (5.6, 5.6, 0.25), (px, 60, 2.95), M("clad_wood"), c)
    box("Pavilion_RoofGlow", (5.0, 5.0, 0.05), (px, 60, 2.9), M("window_soft"), c)
    point_light("Pavilion_Light", (px, 60, 2.4), energy=180, radius=0.6)


def _segments(lo, hi, gaps):
    """Split [lo, hi] into pieces that skip each (centre, width) gap."""
    pieces, cur = [], lo
    for g, w in sorted(gaps):
        a, b = g - w / 2, g + w / 2
        if a > cur:
            pieces.append((cur, min(a, hi)))
        cur = max(cur, b)
    if cur < hi:
        pieces.append((cur, hi))
    return pieces


def road(name, length, width, loc, along_x, c, gaps=()):
    """Road strip with dashed centre line and sidewalks; `gaps` are crossing roads
    as (position along this road, crossing width) where sidewalks/dashes stop."""
    size = (length, width, ROAD_Z + 0.01) if along_x else (width, length, ROAD_Z + 0.01)
    box(name, size, (loc[0], loc[1], -0.01), M("asphalt"), c)
    base = loc[0] if along_x else loc[1]
    pieces = _segments(base - length / 2, base + length / 2, gaps)
    off = width / 2 + 1.1
    k = 0
    for a, b in pieces:
        mid, ln = (a + b) / 2, b - a
        for side in (-1, 1):
            if along_x:
                box(f"{name}_walk{k}_{side}", (ln, 2.2, WALK_H), (mid, loc[1] + side * off, 0), M("sidewalk"), c)
            else:
                box(f"{name}_walk{k}_{side}", (2.2, ln, WALK_H), (loc[0] + side * off, mid, 0), M("sidewalk"), c)
        t = a + 3.0
        while t + 2.2 < b - 2.5:
            p = (t + 1.1, loc[1], ROAD_Z) if along_x else (loc[0], t + 1.1, ROAD_Z)
            sz = (2.2, 0.18, 0.01) if along_x else (0.18, 2.2, 0.01)
            box(f"{name}_dash{k}_{int(t)}", sz, p, M("marking"), c)
            t += 6
        k += 1


def junction(name, x, y, wx, wy, c, zebras=()):
    """Raised junction slab over the overlap of two roads (removes coplanar black artifacts).
    zebras: sides ('n','s','e','w') that get a pedestrian crossing."""
    box(name, (wx, wy, ROAD_Z + 0.016), (x, y, -0.005), M("asphalt_x"), c)
    zt = ROAD_Z + 0.011
    for side in zebras:
        for i in range(7):
            if side in "ns":
                yy = y + (wy / 2 + 1.6) * (1 if side == "n" else -1)
                box(f"{name}_zebra_{side}{i}", (0.55, 2.4, 0.01), (x - wx / 2 + 0.9 + i * (wx - 1.8) / 6, yy, zt), M("curb"), c)
            else:
                xx = x + (wx / 2 + 1.6) * (1 if side == "e" else -1)
                box(f"{name}_zebra_{side}{i}", (2.4, 0.55, 0.01), (xx, y - wy / 2 + 0.8 + i * (wy - 1.6) / 6, zt), M("curb"), c)


def build_roads():
    c = coll("Roads")
    # N-S roads stop their sidewalks at the outer edge of crossing sidewalks (width + 2 x 2.2),
    # E-W sidewalks run on, so sidewalk boxes never overlap.
    road("Avenue", 112, 8, (0, -28), False, c, gaps=[(-30, 11.4), (0, 11.4)])
    road("CrossSt", 140, 7, (0, 0), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("FrontSt", 160, 7, (0, -30), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("LakeSt", 90, 6, (0, 31), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("WestSt", 61, 7, (-34, 0), False, c, gaps=[(-30, 11.4), (0, 11.4), (31, 10.4)])
    road("EastSt", 61, 7, (34, 0), False, c, gaps=[(-30, 11.4), (0, 11.4), (31, 10.4)])
    junction("Junction_Hero", 0, -30, 8, 7, c, zebras="nsew")
    junction("Junction_Lake", 0, 31, 8, 6, c, zebras="s")
    for x in (-34, 34):
        junction(f"Junction_{x}_front", x, -30, 7, 7, c, zebras="n")
        junction(f"Junction_{x}_cross", x, 0, 7, 7, c)
        junction(f"Junction_{x}_lake", x, 31, 7, 6, c)


def build_plaza():
    c = coll("Plaza")
    cyl("Plaza_Base", 10.6, 10.6, 0.24, 48, (0, 0, 0), M("plaza_dark"), c)
    cyl("Plaza_Top", 10.2, 10.2, 0.27, 48, (0, 0, 0), M("plaza"), c)
    cyl("Plaza_RingPave", 9.0, 9.0, 0.28, 48, (0, 0, 0), M("paving_ring"), c)
    cyl("Plaza_Mid", 8.6, 8.6, 0.29, 48, (0, 0, 0), M("plaza"), c)
    cyl("Plaza_GoldRing", 6.7, 6.7, 0.30, 48, (0, 0, 0), M("gold_glow"), c)
    cyl("Plaza_Inner", 6.45, 6.45, 0.31, 48, (0, 0, 0), M("paving_ring"), c)
    cyl("Plaza_InnerTop", 5.6, 5.6, 0.32, 48, (0, 0, 0), M("plaza"), c)
    for i in range(16):  # radial paving joints
        a = i * math.pi / 8
        box(f"Plaza_Joint_{i}", (3.3, 0.12, 0.01), (math.cos(a) * 8.5, math.sin(a) * 8.5, 0.29), M("plaza_dark"), c, rot_z=a)
    # flower ring around the fountain
    cyl("Fountain_Bed", 4.4, 4.4, 0.5, 24, (0, 0, 0.3), M("soil"), c)
    flowers = ["flower_pink", "flower_yellow", "flower_white", "flower_coral", "flower_violet"]
    for i in range(30):
        a = i * 2 * math.pi / 30 + random.uniform(-0.05, 0.05)
        r = random.uniform(3.5, 4.15)
        blob(f"Fountain_Flower_{i}", 0.22, (math.cos(a) * r, math.sin(a) * r, 0.85),
             M(flowers[i % len(flowers)]), c, scale=(1, 1, 0.8))
    # fountain: two tiers
    cyl("Fountain_Base", 3.2, 3.2, 0.8, 16, (0, 0, 0.3), M("plaza_dark"), c)
    cyl("Fountain_Water", 2.85, 2.85, 0.83, 16, (0, 0, 0.3), M("fountain_water"), c)
    cyl("Fountain_Column", 0.5, 0.4, 1.9, 8, (0, 0, 0.3), M("plaza"), c)
    cyl("Fountain_Bowl", 0.6, 1.4, 0.35, 12, (0, 0, 2.1), M("plaza"), c)
    cyl("Fountain_BowlWater", 1.25, 1.25, 0.37, 12, (0, 0, 2.1), M("fountain_water"), c)
    cyl("Fountain_Jet", 0.35, 0.05, 1.7, 6, (0, 0, 2.4), M("fountain_water"), c)
    point_light("Fountain_Glow", (0, 0, 1.7), "#8fd0ff", 300, 1.0)
    # benches facing the fountain
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        x, y = math.cos(a) * 7.6, math.sin(a) * 7.6
        box(f"Bench_{i}", (2.0, 0.6, 0.42), (x, y, 0.32), M("wood"), c, rot_z=a + math.pi / 2)
        bx, by = math.cos(a) * 7.95, math.sin(a) * 7.95
        box(f"Bench_{i}_back", (2.0, 0.12, 0.5), (bx, by, 0.74), M("wood"), c, rot_z=a + math.pi / 2)
    # four planters with cherry trees
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        x, y = math.cos(a) * 8.6, math.sin(a) * 8.6
        cyl(f"Plaza_Planter_{i}", 1.25, 1.25, 0.6, 12, (x, y, 0.3), M("concrete"), c)
        cyl(f"Plaza_Planter_{i}_soil", 1.1, 1.1, 0.62, 12, (x, y, 0.3), M("soil"), c)
        cherry(f"Plaza_Cherry_{i}", (x, y, 0.9), size=0.95)
        for k in range(4):
            b = k * math.pi / 2
            shrub(f"Plaza_Planter_{i}_sh{k}", (x + math.cos(b) * 0.8, y + math.sin(b) * 0.8, 0.9), 0.3)
    # bollard lights on the paving ring + lamps at the plaza edge
    for i in range(12):
        a = i * math.pi / 6
        cyl(f"Bollard_{i}", 0.13, 0.13, 0.6, 8, (math.cos(a) * 9.6, math.sin(a) * 9.6, 0.27), M("bollard"), c)
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4 + 0.32
        lamp(f"PlazaLamp_{i}", (math.cos(a) * 9.9, math.sin(a) * 9.9, 0.27), light=True)


def lamp(name, loc, light=False):
    c = coll("Lamps")
    x, y, z = loc
    cyl(f"{name}_pole", 0.09, 0.07, 4.4, 6, (x, y, z), M("charcoal"), c)
    box(f"{name}_head", (0.55, 0.55, 0.32), (x, y, z + 4.3), M("lamp"), c)
    box(f"{name}_cap", (0.75, 0.75, 0.08), (x, y, z + 4.62), M("charcoal"), c)
    if light:
        point_light(f"{name}_light", (x, y, z + 4.0), energy=220, radius=0.4)


def build_street_lamps():
    for i, y in enumerate(range(-52, -10, 12)):
        lamp(f"AveLamp_L{i}", (-5.5, y, WALK_H), light=(y > -40))
        lamp(f"AveLamp_R{i}", (5.5, y, WALK_H), light=(y > -40))
    for i, x in enumerate(range(-30, 31, 12)):
        if abs(x) < 12:
            continue
        lamp(f"CrossLamp_{i}", (x, 5.0, WALK_H))
        lamp(f"FrontLamp_{i}", (x, -25.0, WALK_H), light=True)
    for i, x in enumerate(range(-42, 43, 12)):
        lamp(f"LakeLamp_{i}", (x, 38.5, WALK_H))


def tree(name, loc, kind=None, size=1.0, c=None):
    c = c or coll("Trees")
    x, y, z = loc
    h = random.uniform(1.6, 2.4) * size
    cyl(f"{name}_trunk", 0.22 * size, 0.16 * size, h, 6, (x, y, z), M("trunk"), c)
    kind = kind or random.choice(["leaf_0", "leaf_1", "leaf_2", "leaf_3", "leaf_0", "leaf_1"])
    r = random.uniform(1.3, 1.9) * size
    if random.random() < 0.3 and kind.startswith("leaf_"):  # slim cone tree
        cyl(f"{name}_crown", r * 0.9, 0.05, r * 3.2, 7, (x, y, z + h * 0.7), M(kind), c)
    else:
        blob(f"{name}_crown", r, (x, y, z + h + r * 0.6), M(kind), c, scale=(1, 1, 1.15))
        if random.random() < 0.5:
            blob(f"{name}_crown2", r * 0.6, (x + r * 0.5, y, z + h + r * 1.2), M(kind), c)


def cherry(name, loc, size=1.0, c=None):
    """Blossoming cherry: short trunk, wide cluster of pink lobes."""
    c = c or coll("Trees")
    x, y, z = loc
    h = 1.5 * size
    cyl(f"{name}_trunk", 0.2 * size, 0.13 * size, h, 6, (x, y, z), M("trunk"), c)
    for k in range(4):
        a = k * math.pi / 2 + random.uniform(0, 0.6)
        r = random.uniform(0.9, 1.25) * size
        off = 0.0 if k == 0 else 0.85 * size
        blob(f"{name}_lobe{k}", r, (x + math.cos(a) * off, y + math.sin(a) * off, z + h + r * 0.55 + (0.4 * size if k == 0 else 0)),
             M("blossom" if k % 2 == 0 else "blossom_light"), c, scale=(1, 1, 0.8))


def shrub(name, loc, r=0.5, c=None):
    c = c or coll("Trees")
    return blob(name, r, (loc[0], loc[1], loc[2] + r * 0.45), M(random.choice(["shrub", "shrub_dark"])), c,
                scale=(1.15, 1, 0.75), jitter=0.15)


def flowerbed(name, loc, w, d, c, rot_z=0.0, parent=None):
    """Raised soil bed with a few low-poly flower clusters (local to `parent` when given)."""
    box(f"{name}_edge", (w, d, 0.28), loc, M("curb"), c, rot_z=rot_z, parent=parent)
    box(f"{name}_soil", (w - 0.2, d - 0.2, 0.3), loc, M("soil"), c, rot_z=rot_z, parent=parent)
    colors = ["flower_pink", "flower_yellow", "flower_white", "flower_coral", "flower_violet"]
    n = max(3, int(w * d * 1.4))
    for i in range(n):
        fx = loc[0] + random.uniform(-w / 2 + 0.25, w / 2 - 0.25)
        fy = loc[1] + random.uniform(-d / 2 + 0.25, d / 2 - 0.25)
        b = blob(f"{name}_f{i}", 0.2, (fx, fy, loc[2] + 0.38), M(random.choice(colors)), c, scale=(1, 1, 0.8))
        if parent:
            b.parent = parent


# --------------------------------------------------------------------------- houses & plots

PALETTES = [  # (main wall, accent cladding)
    ("wall_white", "clad_wood"), ("wall_sand", "clad_dark"), ("clad_dark", "clad_wood"),
    ("wall_grey", "clad_wood"), ("wall_blush", "clad_dark"), ("wall_cream", "clad_dark"),
]
STYLE_NAMES = ["cantilever", "monopitch", "pavilion", "gable", "stacked"]


def windows(parent, w, d, z0, h, c, tag, step=1.9, front=True):
    """Glowing window panes on the facades of a w x d volume (front = -Y)."""
    n = max(1, int(w // step))
    for i in range(n):
        x = -w / 2 + (i + 0.5) * w / n
        for side in ((-1, 1) if front else (1,)):
            if random.random() < 0.15:
                continue
            m = M("window") if random.random() < 0.75 else M("window_soft")
            box(f"{tag}_win_{i}_{side}", (w / n * 0.6, 0.08, h), (x, side * d / 2, z0), m, c, parent=parent)
    nd = max(1, int(d // step))
    for i in range(nd):
        y = -d / 2 + (i + 0.5) * d / nd
        for side in (-1, 1):
            if random.random() < 0.35:
                continue
            box(f"{tag}_swin_{i}_{side}", (0.08, d / nd * 0.55, h), (side * w / 2, y, z0), M("window"), c, parent=parent)


def _win_group(root, w, d, cy, z0, h, c, tag, xoff=0.0, step=1.9, front=True):
    g = bpy.data.objects.new(f"{tag}_windows", None)
    c.objects.link(g)
    g.parent = root
    g.location = (xoff, cy, 0)
    windows(g, w + 0.02, d + 0.02, z0, h, c, tag, step, front)


def panoramic(root, tag, c, x, yf, z0, w, h, n=3):
    """Floor-to-ceiling glazing with dark frames on a facade at y = yf (front facing -Y)."""
    box(f"{tag}_glass", (w, 0.08, h), (x, yf - 0.03, z0), M("window"), c, parent=root)
    for i in range(n + 1):
        mx = x - w / 2 + i * w / n
        box(f"{tag}_mull{i}", (0.09, 0.14, h), (mx, yf - 0.06, z0), M("mullion"), c, parent=root)
    box(f"{tag}_head", (w + 0.1, 0.14, 0.1), (x, yf - 0.06, z0 + h - 0.05), M("mullion"), c, parent=root)
    box(f"{tag}_sill", (w + 0.1, 0.16, 0.08), (x, yf - 0.06, z0), M("mullion"), c, parent=root)


def balcony(root, tag, c, x, yf, z, w, depth=1.2):
    box(f"{tag}_slab", (w, depth, 0.18), (x, yf - depth / 2, z), M("charcoal"), c, parent=root)
    box(f"{tag}_rail", (w, 0.05, 0.95), (x, yf - depth + 0.03, z + 0.18), M("glass"), c, parent=root)
    box(f"{tag}_handrail", (w, 0.09, 0.06), (x, yf - depth + 0.03, z + 1.13), M("mullion"), c, parent=root)
    for sx in (-1, 1):
        box(f"{tag}_rail_s{sx}", (0.05, depth, 0.95), (x + sx * w / 2, yf - depth / 2, z + 0.18), M("glass"), c, parent=root)


def fins(root, tag, c, x0, x1, yf, z0, h, n=5):
    for i in range(n):
        fx = x0 + (i + 0.5) * (x1 - x0) / n
        box(f"{tag}_fin{i}", (0.12, 0.35, h), (fx, yf - 0.17, z0), M("clad_wood"), c, parent=root)


def gable_body(name, w, d, hw, hr, loc, material, c, parent):
    """Modern barn volume: pentagon prism with the ridge along Y (gable faces the street)."""
    bm = bmesh.new()
    prof = [(-w / 2, 0), (w / 2, 0), (w / 2, hw), (0, hw + hr), (-w / 2, hw)]
    front = [bm.verts.new((px, -d / 2, pz)) for px, pz in prof]
    back = [bm.verts.new((px, d / 2, pz)) for px, pz in prof]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    for i in range(5):
        j = (i + 1) % 5
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, material, c, loc, 0.0, parent)


def gable_roof(tag, c, root, x, cy, w, d, hw, hr):
    slope = math.atan2(hr, w / 2)
    ln = math.hypot(w / 2, hr) + 0.45
    for sx in (-1, 1):
        r = box(f"{tag}_roof{sx}", (ln, d + 0.7, 0.2), (x + sx * w / 4, cy, hw + hr / 2 + 0.04), M("roof_metal"), c, parent=root)
        r.rotation_euler.y = slope if sx > 0 else -slope


def house(idx, x, y, face_south, style):
    c = coll("Houses")
    tag = f"House_{idx:02d}_{STYLE_NAMES[style]}"
    root = bpy.data.objects.new(tag, None)
    c.objects.link(root)
    root.location = (x, y, WALK_H)
    root.rotation_euler.z = 0 if face_south else math.pi
    wall_name, accent_name = PALETTES[idx % len(PALETTES)]
    wall, accent = M(wall_name), M(accent_name)

    # lot: lawn, driveway, path, hedge, shrubs, flower bed
    box(f"{tag}_lawn", (10.2, 8.4, 0.06), (0, 0, -0.04), M("grass_lawn"), c, parent=root)
    box(f"{tag}_drive", (2.8, 2.7, 0.08), (3.9, -2.85, -0.04), M("concrete"), c, parent=root)
    box(f"{tag}_path", (1.2, 1.6, 0.08), (-0.6, -3.4, -0.04), M("sidewalk"), c, parent=root)
    box(f"{tag}_hedge_back", (10.0, 0.5, 0.75), (0, 3.95, 0), M("hedge"), c, parent=root)
    flowerbed(f"{tag}_bed", (-3.2, -3.35, 0), 2.6, 0.9, c, parent=root)
    for k in range(3):
        sh = shrub(f"{tag}_shrub{k}", (-4.6 + k * 0.0, -2.2 + k * 1.3, 0), 0.45, c)
        sh.parent = root

    W = random.uniform(6.8, 7.6)
    D = random.uniform(5.0, 5.6)
    gy = 0.6
    yf = gy - D / 2
    garage = True

    if style == 0:      # cantilever: white base, clad upper volume overhanging the front
        box(f"{tag}_ground", (W, D, 3.1), (0, gy, 0), wall, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, -W * 0.12, yf, 0.3, W * 0.55, 2.45, 3)
        _win_group(root, W, D, gy, 0.6, 1.9, c, f"{tag}_g", front=False)
        box(f"{tag}_roof_g", (W + 0.3, D + 0.3, 0.2), (0, gy, 3.1), M("charcoal"), c, parent=root)
        uw, ud, ux = W * 0.68, D + 1.0, W * 0.16
        uy = gy - 0.5
        box(f"{tag}_upper", (uw, ud, 2.8), (ux, uy, 3.3), accent, c, parent=root)
        panoramic(root, f"{tag}_upano", c, ux - uw * 0.14, uy - ud / 2, 3.6, uw * 0.62, 2.0, 2)
        fins(root, f"{tag}_ufin", c, ux + uw * 0.2, ux + uw / 2 - 0.1, uy - ud / 2, 3.3, 2.8, 4)
        _win_group(root, uw, ud, uy, 3.8, 1.6, c, f"{tag}_u", xoff=ux, front=False)
        box(f"{tag}_roof", (uw + 0.4, ud + 0.4, 0.26), (ux, uy, 6.1), M("roof"), c, parent=root)
        tx = -W / 2 + (W / 2 - uw / 2 + ux) / 2
        box(f"{tag}_terrace_rail", (W / 2 - uw / 2 + ux - 0.2, 0.05, 0.9), (tx, yf + 0.1, 3.3), M("glass"), c, parent=root)
    elif style == 1:    # mono-pitch: two storeys, full-width glazing, balcony, wood band
        box(f"{tag}_body", (W, D, 6.0), (0, gy, 0), wall, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, W * 0.14, yf, 0.3, W * 0.6, 2.5, 3)
        box(f"{tag}_wood", (W * 0.3, 0.1, 6.0), (-W / 2 + W * 0.15, yf - 0.05, 0), accent, c, parent=root)
        panoramic(root, f"{tag}_upano", c, W * 0.14, yf, 3.35, W * 0.5, 2.2, 2)
        balcony(root, f"{tag}_balc", c, W * 0.14, yf, 3.1, W * 0.58, 1.2)
        _win_group(root, W, D, gy, 0.6, 1.9, c, f"{tag}_g", front=False)
        _win_group(root, W, D, gy, 3.6, 1.6, c, f"{tag}_u", front=False)
        r = box(f"{tag}_roof", (W + 0.8, D + 1.0, 0.25), (0, gy, 6.15), M("roof"), c, parent=root)
        r.rotation_euler.x = math.radians(9)
    elif style == 2:    # pavilion: wide single storey, deep roof overhang, all-glass front, roof studio + pergola
        W2 = W + 0.6
        box(f"{tag}_body", (W2, D, 3.3), (0, gy, 0), wall, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, -0.2, yf, 0.25, W2 * 0.8, 2.8, 5)
        _win_group(root, W2, D, gy, 0.6, 2.0, c, f"{tag}_g", front=False)
        box(f"{tag}_roof", (W2 + 1.4, D + 1.8, 0.3), (0, gy - 0.3, 3.3), M("charcoal"), c, parent=root)
        box(f"{tag}_fascia", (W2 + 1.4, 0.12, 0.18), (0, gy - 0.3 - (D + 1.8) / 2, 3.42), accent, c, parent=root)
        box(f"{tag}_studio", (W2 * 0.4, D * 0.55, 2.3), (-W2 * 0.22, gy + 0.7, 3.6), M("glass"), c, parent=root)
        _win_group(root, W2 * 0.4, D * 0.55, gy + 0.7, 3.8, 1.8, c, f"{tag}_u", xoff=-W2 * 0.22, step=1.2)
        box(f"{tag}_studio_roof", (W2 * 0.4 + 0.5, D * 0.55 + 0.5, 0.2), (-W2 * 0.22, gy + 0.7, 5.9), M("charcoal"), c, parent=root)
        for k in range(6):  # pergola over the roof terrace
            box(f"{tag}_perg{k}", (0.12, D * 0.7, 0.14), (W2 * 0.08 + k * 0.55, gy, 5.55), M("clad_wood"), c, parent=root)
        for sx in (W2 * 0.06, W2 * 0.06 + 2.9):
            box(f"{tag}_pergpost{sx:.1f}", (0.12, 0.12, 1.95), (sx, gy - D * 0.33, 3.6), M("clad_wood"), c, parent=root)
        garage = False
    elif style == 3:    # modern gable: dark barn volume with gable glazing + white flat-roof wing
        bw = W * 0.62
        bx = -W * 0.18
        gable_body(f"{tag}_barn", bw, D + 0.4, 3.3, 2.3, (bx, gy, 0), accent if accent_name == "clad_dark" else M("clad_dark"), c, root)
        gable_roof(tag, c, root, bx, gy, bw, D + 0.4, 3.3, 2.3)
        panoramic(root, f"{tag}_gpano", c, bx, gy - (D + 0.4) / 2, 0.25, bw * 0.55, 4.3, 3)
        _win_group(root, bw, D + 0.4, gy, 0.6, 1.9, c, f"{tag}_g", xoff=bx, front=False)
        ww = W * 0.42
        wx = bx + bw / 2 + ww / 2
        box(f"{tag}_wing", (ww, D - 0.6, 2.9), (wx, gy + 0.3, 0), wall, c, parent=root)
        panoramic(root, f"{tag}_wpano", c, wx, gy + 0.3 - (D - 0.6) / 2, 0.3, ww * 0.7, 2.2, 2)
        box(f"{tag}_wing_roof", (ww + 0.3, D - 0.3, 0.2), (wx, gy + 0.3, 2.9), M("charcoal"), c, parent=root)
        garage = False
    else:               # stacked: white ground cube, rotated timber upper cube, corner glazing
        gw = W * 0.8
        gx = -W * 0.1
        box(f"{tag}_ground", (gw, D, 3.1), (gx, gy, 0), wall, c, parent=root)
        panoramic(root, f"{tag}_corner_f", c, gx - gw / 2 + 1.3, yf, 0.3, 2.5, 2.45, 2)
        box(f"{tag}_corner_s", (0.08, 2.4, 2.45), (gx - gw / 2 - 0.03, yf + 1.25, 0.3), M("window"), c, parent=root)
        _win_group(root, gw, D, gy, 0.6, 1.9, c, f"{tag}_g", xoff=gx, front=False)
        box(f"{tag}_roof_g", (gw + 0.3, D + 0.3, 0.2), (gx, gy, 3.1), M("charcoal"), c, parent=root)
        uw, ud = W * 0.55, D * 0.95
        ux, uy = gx + gw * 0.18, gy + 0.35
        box(f"{tag}_upper", (uw, ud, 2.9), (ux, uy, 3.3), M("clad_wood"), c, parent=root)
        panoramic(root, f"{tag}_upano", c, ux, uy - ud / 2, 3.55, uw * 0.78, 2.3, 3)
        _win_group(root, uw, ud, uy, 3.8, 1.6, c, f"{tag}_u", xoff=ux, front=False)
        box(f"{tag}_roof", (uw + 0.3, ud + 0.3, 0.22), (ux, uy, 6.2), M("charcoal"), c, parent=root)
        box(f"{tag}_terrace_rail", (gw * 0.4, 0.05, 0.9), (gx - gw * 0.28, yf + 0.1, 3.3), M("glass"), c, parent=root)
        for k in range(2):
            sh = shrub(f"{tag}_roofplant{k}", (gx - gw * 0.38 + k * 1.2, gy + 1.2, 3.3), 0.4, c)
            sh.parent = root

    # entrance (on the main volume front)
    if style != 3:
        box(f"{tag}_door", (1.05, 0.12, 2.25), (-W * 0.5 + 1.0 if style != 1 else -W * 0.3, yf - 0.02, 0), M("wood"), c, parent=root)
        box(f"{tag}_porch", (0.25, 0.12, 0.25), (-W * 0.5 + 1.8 if style != 1 else -W * 0.3 + 0.8, yf - 0.08, 2.1), M("lamp"), c, parent=root)

    if garage:
        box(f"{tag}_garage", (3.0, 4.2, 2.6), (W / 2 + 1.35, gy + 0.2, 0), M("charcoal"), c, parent=root)
        box(f"{tag}_garage_door", (2.4, 0.1, 2.1), (W / 2 + 1.35, gy + 0.2 - 2.12, 0), M("concrete"), c, parent=root)
        box(f"{tag}_garage_light", (2.4, 0.1, 0.08), (W / 2 + 1.35, gy + 0.2 - 2.16, 2.3), M("rail_glow"), c, parent=root)
    else:               # carport: slim roof on posts
        box(f"{tag}_carport", (3.2, 4.6, 0.18), (W / 2 + 1.35, gy - 0.2, 2.6), M("clad_wood"), c, parent=root)
        for py in (-2.0, 2.0):
            box(f"{tag}_cp_post{py}", (0.12, 0.12, 2.6), (W / 2 + 2.8, gy - 0.2 + py, 0), M("charcoal"), c, parent=root)

    # yard tree: half the lots get a blossoming cherry
    ty = (x - 4.2 if face_south else x + 4.2, y + (2.9 if face_south else -2.9), WALK_H)
    if idx % 2 == 0:
        cherry(f"{tag}_cherry", ty, size=0.85)
    else:
        tree(f"{tag}_yardtree", ty, size=0.8)


def free_plot(idx, x, y):
    c = coll("FreePlots")
    tag = f"FreePlot_{idx:02d}"
    root = bpy.data.objects.new(tag, None)
    c.objects.link(root)
    root.location = (x, y, WALK_H)
    box(f"{tag}_soil", (9.6, 7.8, 0.06), (0, 0, -0.03), M("dirt"), c, parent=root)
    for sx, sy, w, d in ((0, 3.9, 9.6, 0.14), (0, -3.9, 9.6, 0.14), (4.8, 0, 0.14, 7.8), (-4.8, 0, 0.14, 7.8)):
        # dashed golden boundary
        n = 6 if w > d else 5
        L = max(w, d)
        for i in range(n):
            t = -L / 2 + (i + 0.5) * L / n
            p = (sx + t, sy, 0.03) if w > d else (sx, sy + t, 0.03)
            s = (L / n * 0.6, 0.14, 0.05) if w > d else (0.14, L / n * 0.6, 0.05)
            box(f"{tag}_edge_{sx}_{sy}_{i}", s, p, M("gold_glow"), c, parent=root)
    # corner stakes + floating "+" marker
    for cx in (-4.8, 4.8):
        for cyy in (-3.9, 3.9):
            box(f"{tag}_stake_{cx}_{cyy}", (0.16, 0.16, 0.7), (cx, cyy, 0), M("wood"), c, parent=root)
    cyl(f"{tag}_marker_pole", 0.06, 0.06, 1.9, 6, (0, -2.6, 0), M("charcoal"), c, parent=root)
    box(f"{tag}_marker_bg", (1.4, 0.1, 1.4), (0, -2.6, 1.9), M("charcoal"), c, parent=root)
    box(f"{tag}_plus_h", (0.9, 0.14, 0.2), (0, -2.68, 2.5), M("gold_glow"), c, parent=root)
    box(f"{tag}_plus_v", (0.2, 0.14, 0.9), (0, -2.68, 2.15), M("gold_glow"), c, parent=root)


def build_lots():
    xs, ys = (12.0, 23.4), (10.6, 20.4)
    lots = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for x in xs:
                for y in ys:
                    lots.append((sx * x, sy * y))
    free = {(-23.4, -20.4), (12.0, -10.6), (23.4, 20.4), (-12.0, 20.4)}
    h = p = 0
    for (x, y) in lots:
        if (x, y) in free:
            p += 1
            free_plot(p, x, y)
        else:
            h += 1
            house(h, x, y, face_south=(y > 0) ^ (abs(y) > 15), style=(h * 3) % 5)
    return h, p


def build_greenery():
    # trees along streets
    i = 0
    for x in range(-62, 63, 7):
        if abs(x) > 6 and random.random() < 0.85:
            tree(f"T_front_{i}", (x + random.uniform(-1, 1), -36.5, 0)); i += 1
    for y in range(-26, 27, 8):
        for xx in (-38.5, 38.5):
            tree(f"T_side_{i}", (xx, y, 0)); i += 1
    # corner gardens around the plaza (between plaza and lots)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cherry(f"T_corner_{sx}_{sy}", (sx * 7.6, sy * 7.4, WALK_H), size=0.75)
    # shrubs and flower beds along the front street (foreground)
    for k, x in enumerate(range(-30, 31, 4)):
        if abs(x) < 8:
            continue
        shrub(f"S_front_{k}", (x + random.uniform(-0.6, 0.6), -23.8, WALK_H), random.uniform(0.4, 0.6))
    for k, x in enumerate((-15, -25, 15, 25)):
        flowerbed(f"Bed_front_{k}", (x, -36.6, 0), 3.2, 1.0, coll("Trees"))
    # flowering trees along the avenue approach
    for k, y in enumerate(range(-58, -38, 7)):
        cherry(f"T_ave_L{k}", (-7.6, y, 0), size=0.9)
        cherry(f"T_ave_R{k}", (7.6, y, 0), size=0.9)
    # foreground clusters & meadows
    for k in range(140):
        x = random.uniform(-110, 110)
        y = random.uniform(-110, -38)
        if abs(x) < 7 or abs(y + 30) < 7:
            continue
        if random.random() < 0.15:
            cherry(f"T_meadow_{k}", (x, y, 0), size=random.uniform(0.9, 1.3))
            continue
        kind = "leaf_gold" if random.random() < 0.1 else None
        tree(f"T_meadow_{k}", (x, y, 0), kind=kind, size=random.uniform(0.9, 1.5))
    for k in range(60):
        x = random.choice([random.uniform(-110, -42), random.uniform(42, 110)])
        y = random.uniform(-36, 33)
        tree(f"T_edge_{k}", (x, y, 0), size=random.uniform(0.9, 1.4))
    # hero foreground framing trees (bottom corners of the vertical frame)
    cherry("T_hero_L", (-17.5, -44, 0), size=1.3)
    tree("T_hero_R", (13, -42, 0), kind="leaf_gold", size=1.1)


def build_background():
    c = coll("Background")
    # skyline across the lake
    random_state = random.getstate()
    random.seed(77)
    x = -120
    k = 0
    while x < 300:
        w = random.uniform(7, 15)
        d = random.uniform(7, 14)
        center = 1 - min(abs(x - 110) / 170, 1)
        h = random.uniform(10, 20) + center * random.uniform(12, 40)
        y = random.uniform(300, 335)
        box(f"Tower_{k}", (w, d, h), (x, y, -0.9), M("tower_lit"), c)
        if random.random() < 0.35:
            box(f"Tower_{k}_crown", (w * 0.6, d * 0.6, h * 0.15), (x, y, h - 0.9), M("tower_lit"), c)
        if random.random() < 0.3:
            box(f"Tower_{k}_beacon", (0.6, 0.6, 1.5), (x, y, h * 1.15 - 0.9), M("lamp"), c)
        x += w + random.uniform(1, 6)
        k += 1
    # far shore strip
    box("FarShore", (900, 70, 0.6), (0, 318, -0.9), M("grass"), c)
    for k in range(60):  # dark tree line on the far shore
        blob(f"FarTree_{k}", random.uniform(3, 5), (-250 + k * 9 + random.uniform(-3, 3), 286, 0.5), M("shrub_dark"), c,
             scale=(1, 1, 0.8))
    # low-poly mountains
    # soft, wide ridges (not peaks): flattened low-poly hills in two layers
    for j in range(16):
        far = j % 2 == 0
        mx = -600 + j * 80 + random.uniform(-30, 30)
        my = random.uniform(620, 700) if far else random.uniform(430, 500)
        hgt = random.uniform(40, 70) if far else random.uniform(22, 40)
        r = random.uniform(150, 220)
        ridge = blob(f"Ridge_{j}", 1.0, (mx, my, -2), M("mountain_far" if far else "mountain_near"), c,
                     scale=(r, r * 0.5, hgt), jitter=0.18)
        ridge.rotation_euler.z = random.uniform(-0.3, 0.3)
    random.setstate(random_state)


# --------------------------------------------------------------------------- camera & render

def build_camera():
    cam = bpy.data.cameras.new("Cam_Reels")
    cam.lens = 30
    cam.sensor_fit = "VERTICAL"
    cam.sensor_height = 36
    cam.clip_end = 3000
    ob = bpy.data.objects.new("Cam_Reels", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector((-18, -66, 31))
    target = Vector((3, 7, 0))
    ob.rotation_euler = (target - ob.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob


def setup_render(args):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = args.samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.03
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 6
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.render.resolution_x = 1080
    s.render.resolution_y = 1920
    s.render.resolution_percentage = 50 if args.preview else 100
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    s.view_settings.view_transform = "AgX"
    try:
        s.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    s.view_settings.exposure = 0.4
    # mist pass drives a soft aerial haze that separates the district from the skyline
    s.view_layers[0].use_pass_mist = True
    s.world.mist_settings.start = 60
    s.world.mist_settings.depth = 900
    s.world.mist_settings.falloff = "LINEAR"
    # cozy bloom on lamps / windows / sun
    s.use_nodes = True
    nt = s.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.9
    glare.size = 9
    glare.mix = -0.2
    ramp = nt.nodes.new("CompositorNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0, 0, 0, 1)
    els[1].position, els[1].color = 1.0, (0, 0, 0, 1)      # sky (mist = 1) stays untouched
    for pos, v in ((0.25, 0.1), (0.9, 0.38), (0.985, 0.38)):
        e = els.new(pos)
        e.color = (v, v, v, 1)
    haze = nt.nodes.new("CompositorNodeMixRGB")
    haze.inputs[2].default_value = (*srgb("#c98ba6"), 1)
    out = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    nt.links.new(rl.outputs["Mist"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Image"], haze.inputs["Fac"])
    nt.links.new(glare.outputs["Image"], haze.inputs[1])
    nt.links.new(haze.outputs["Image"], out.inputs["Image"])


# --------------------------------------------------------------------------- main

def main():
    args = parse_args()
    random.seed(args.seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_materials()
    build_world()
    build_lights()
    build_ground_and_water()
    build_roads()
    build_plaza()
    build_street_lamps()
    houses, plots = build_lots()
    build_greenery()
    build_background()
    build_camera()
    setup_render(args)
    print(f"[NOC] district built: {houses} houses, {plots} free plots, "
          f"{len(bpy.data.objects)} objects")
    if args.save:
        path = os.path.abspath(args.save)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        print(f"[NOC] saved {path}")
    if args.render:
        path = os.path.abspath(args.render)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"[NOC] rendered {path}")


if __name__ == "__main__":
    main()
