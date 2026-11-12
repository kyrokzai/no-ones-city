"""NO ONE'S CITY — Episode 001 / M0.1: first low-poly district.

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
    mat("asphalt", "#262a36", 0.8)
    mat("marking", "#e8c37a", 0.6)
    mat("sidewalk", "#b9a58c", 0.75)
    mat("plaza", "#d8c3a2", 0.65)
    mat("plaza_dark", "#8a7660", 0.7)
    mat("gold_glow", "#f5b04a", 0.4, emit="#ffb347", strength=6.0)
    mat("water", "#1b3150", 0.04, spec=0.8)
    mat("fountain_water", "#6fb6e6", 0.05, emit="#7cc8ff", strength=1.5)
    mat("trunk", "#5a3d2b", 0.9)
    for i, c in enumerate(["#4d7a32", "#5f8c3a", "#3f6b30", "#6e9640"]):
        mat(f"leaf_{i}", c, 0.85)
    mat("leaf_pink", "#e89ab4", 0.8)
    mat("leaf_gold", "#d9a441", 0.8)
    mat("hedge", "#3c6630", 0.9)
    for i, c in enumerate(["#efe6d8", "#e4ddd2", "#d9cdbb", "#f3eee6", "#cfc6b8"]):
        mat(f"wall_{i}", c, 0.7)
    mat("wood", "#9a6440", 0.6)
    mat("charcoal", "#2c2f38", 0.6)
    mat("roof", "#3a3d47", 0.7)
    mat("window", "#ffcf8a", 0.2, emit="#ffbe6b", strength=4.0)
    mat("window_cool", "#bcd6ff", 0.15, emit="#9ec3ff", strength=1.2)
    mat("glass", "#86a6c4", 0.08, spec=0.9)
    mat("concrete", "#a39c92", 0.8)
    mat("dirt", "#8a6a48", 0.95)
    mat("lamp", "#ffd9a0", 0.3, emit="#ffc977", strength=20.0)
    mat("mountain_far", "#b07a9a", 0.95)
    mat("mountain_near", "#6e4f7e", 0.95)
    mat("sun_disc", "#ffb24a", 0.5, emit="#ffa63d", strength=7.0)
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
    b.inputs["Emission Strength"].default_value = 1.1
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
    stops = [(0.0, "#ffb85a"), (0.04, "#ffa060"), (0.1, "#f08a8c"), (0.17, "#c870a6"),
             (0.26, "#5b3f7a"), (0.5, "#1c2350"), (1.0, "#0a1028")]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], (*srgb(stops[0][1]), 1)
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*srgb(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = (*srgb(col), 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.5
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


SUN_POS = Vector((215, 900, 105))


def build_lights():
    c = coll("Lights")
    sun = bpy.data.lights.new("Sun_Golden", "SUN")
    sun.color = srgb("#ffb070")
    sun.energy = 6.0
    sun.angle = math.radians(3)
    ob = bpy.data.objects.new("Sun_Golden", sun)
    c.objects.link(ob)
    d = (Vector((0, 0, 0)) - SUN_POS).normalized()
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # cool rim / fill from the opposite side (navy sky bounce)
    fill = bpy.data.lights.new("Fill_Navy", "SUN")
    fill.color = srgb("#6f86d6")
    fill.energy = 0.35
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
    # lake + quay
    box("Lake", (1200, 1200, 0.05), (0, 640, -0.9), M("water"), c)
    box("Quay_Wall", (700, 1.2, 1.05), (0, 40.6, -0.9), M("concrete"), c)
    box("Promenade", (700, 6, WALK_H), (0, 37, 0), M("sidewalk"), c)
    box("Promenade_Glow", (700, 0.12, 0.05), (0, 40.0, WALK_H), M("gold_glow"), c)


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
        t = a + 2.5
        while t + 2.2 < b - 1.5:
            p = (t + 1.1, loc[1], ROAD_Z) if along_x else (loc[0], t + 1.1, ROAD_Z)
            sz = (2.2, 0.18, 0.01) if along_x else (0.18, 2.2, 0.01)
            box(f"{name}_dash{k}_{int(t)}", sz, p, M("marking"), c)
            t += 6
        k += 1


def build_roads():
    c = coll("Roads")
    # main N-S avenue into the plaza, ends at the lake street (T-junction)
    road("Avenue", 112, 8, (0, -28), False, c, gaps=[(-30, 7), (0, 7)])
    road("CrossSt", 140, 7, (0, 0), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("FrontSt", 160, 7, (0, -30), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("LakeSt", 90, 6, (0, 31), True, c, gaps=[(-34, 7), (0, 8), (34, 7)])
    road("WestSt", 61, 7, (-34, 0), False, c, gaps=[(-30, 7), (0, 7), (31, 6)])
    road("EastSt", 61, 7, (34, 0), False, c, gaps=[(-30, 7), (0, 7), (31, 6)])
    # zebra crossing on the hero intersection (avenue x front street)
    for i in range(7):
        box(f"Zebra_{i}", (0.6, 2.6, 0.01), (-3 + i, -25.0, ROAD_Z), M("plaza"), c)


def build_plaza():
    c = coll("Plaza")
    cyl("Plaza_Base", 10.5, 10.5, 0.24, 40, (0, 0, 0), M("plaza_dark"), c)
    cyl("Plaza_Top", 10.0, 10.0, 0.27, 40, (0, 0, 0), M("plaza"), c)
    cyl("Plaza_GoldRing", 6.6, 6.6, 0.29, 40, (0, 0, 0), M("gold_glow"), c)
    cyl("Plaza_Inner", 6.35, 6.35, 0.30, 40, (0, 0, 0), M("plaza"), c)
    # fountain
    cyl("Fountain_Base", 3.2, 3.2, 0.75, 16, (0, 0, 0.3), M("plaza_dark"), c)
    cyl("Fountain_Water", 2.85, 2.85, 0.78, 16, (0, 0, 0.3), M("fountain_water"), c)
    cyl("Fountain_Column", 0.5, 0.4, 1.9, 8, (0, 0, 0.3), M("plaza"), c)
    cyl("Fountain_Bowl", 0.6, 1.3, 0.35, 12, (0, 0, 2.1), M("plaza"), c)
    cyl("Fountain_BowlWater", 1.15, 1.15, 0.37, 12, (0, 0, 2.1), M("fountain_water"), c)
    cyl("Fountain_Jet", 0.35, 0.05, 1.6, 6, (0, 0, 2.4), M("fountain_water"), c)
    point_light("Fountain_Glow", (0, 0, 1.6), "#8fd0ff", 250, 1.0)
    # benches and lamps around the plaza
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        x, y = math.cos(a) * 8.2, math.sin(a) * 8.2
        box(f"Bench_{i}", (2.0, 0.6, 0.45), (x, y, 0.3), M("wood"), c, rot_z=a + math.pi / 2)
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        lamp(f"PlazaLamp_{i}", (math.cos(a) * 9.4, math.sin(a) * 9.4, 0.27), light=True)


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


# --------------------------------------------------------------------------- houses & plots

WALLS = ["wall_0", "wall_1", "wall_2", "wall_3", "wall_4"]


def windows(parent, w, d, z0, h, c, tag, step=1.9):
    """Glowing window panes on all four facades of a w x d volume."""
    n = max(1, int(w // step))
    for i in range(n):
        x = -w / 2 + (i + 0.5) * w / n
        for side in (-1, 1):
            if random.random() < 0.15:
                continue
            m = M("window") if random.random() < 0.8 else M("window_cool")
            box(f"{tag}_win_{i}_{side}", (w / n * 0.62, 0.08, h), (x, side * d / 2, z0), m, c, parent=parent)
    nd = max(1, int(d // step))
    for i in range(nd):
        y = -d / 2 + (i + 0.5) * d / nd
        for side in (-1, 1):
            if random.random() < 0.35:
                continue
            box(f"{tag}_swin_{i}_{side}", (0.08, d / nd * 0.55, h), (side * w / 2, y, z0), M("window"), c, parent=parent)


def house(idx, x, y, face_south, style):
    c = coll("Houses")
    tag = f"House_{idx:02d}"
    root = bpy.data.objects.new(tag, None)
    c.objects.link(root)
    root.location = (x, y, WALK_H)
    root.rotation_euler.z = 0 if face_south else math.pi
    wall = M(WALLS[idx % len(WALLS)])

    # lot: lawn, driveway, hedges
    box(f"{tag}_lawn", (10.2, 8.4, 0.06), (0, 0, -0.04), M("grass_lawn"), c, parent=root)
    box(f"{tag}_drive", (2.6, 2.6, 0.08), (3.6, -2.9, -0.04), M("concrete"), c, parent=root)
    box(f"{tag}_path", (1.2, 1.6, 0.08), (-0.4, -3.4, -0.04), M("sidewalk"), c, parent=root)
    box(f"{tag}_hedge_back", (10.0, 0.5, 0.75), (0, 3.95, 0), M("hedge"), c, parent=root)

    W = random.uniform(6.6, 7.6)
    D = random.uniform(5.0, 5.8)
    gy = 0.6
    box(f"{tag}_ground", (W, D, 3.1), (0, gy, 0), wall, c, parent=root)
    # ground-floor windows (front & back) + sides
    _win_group(root, W, D, gy, 0.6, 1.9, c, f"{tag}_g")
    box(f"{tag}_door", (1.05, 0.12, 2.2), (-0.4, gy - D / 2 - 0.02, 0), M("wood"), c, parent=root)
    box(f"{tag}_canopy", (2.2, 1.2, 0.14), (-0.4, gy - D / 2 - 0.5, 2.55), M("charcoal"), c, parent=root)

    if style == 0:      # cantilevered upper floor, flat roofs
        uw, ud, ux = W * 0.68, D + 0.6, W * 0.2
        box(f"{tag}_upper", (uw, ud, 2.9), (ux, gy - 0.3, 3.1), wall, c, parent=root)
        _win_group(root, uw, ud, gy - 0.3, 3.6, 1.7, c, f"{tag}_u", xoff=ux)
        box(f"{tag}_roof", (uw + 0.5, ud + 0.5, 0.28), (ux, gy - 0.3, 6.0), M("roof"), c, parent=root)
        box(f"{tag}_roof_g", (W + 0.4, D + 0.4, 0.22), (0, gy, 3.1), M("charcoal"), c, parent=root)
        box(f"{tag}_wood", (0.9, 0.1, 2.9), (ux + uw / 2 - 0.6, gy - 0.3 - ud / 2 - 0.06, 3.1), M("wood"), c, parent=root)
    elif style == 1:    # full two storeys with mono-pitch roof and wood cladding
        box(f"{tag}_upper", (W, D, 2.8), (0, gy, 3.1), wall, c, parent=root)
        _win_group(root, W, D, gy, 3.6, 1.6, c, f"{tag}_u")
        r = box(f"{tag}_roof", (W + 0.8, D + 0.9, 0.25), (0, gy, 6.15), M("roof"), c, parent=root)
        r.rotation_euler.x = math.radians(9)
        box(f"{tag}_wood", (W * 0.35, 0.1, 5.9), (-W / 2 + W * 0.175, gy - D / 2 - 0.06, 0), M("wood"), c, parent=root)
    else:               # single storey + glass terrace box + side garage
        box(f"{tag}_roof", (W + 0.6, D + 0.6, 0.25), (0, gy, 3.1), M("roof"), c, parent=root)
        box(f"{tag}_studio", (W * 0.45, D * 0.6, 2.4), (-W * 0.2, gy + 0.6, 3.35), M("glass"), c, parent=root)
        _win_group(root, W * 0.45, D * 0.6, gy + 0.6, 3.6, 1.8, c, f"{tag}_u", xoff=-W * 0.2, step=1.2)
        box(f"{tag}_studio_roof", (W * 0.45 + 0.5, D * 0.6 + 0.5, 0.2), (-W * 0.2, gy + 0.6, 5.75), M("charcoal"), c, parent=root)
        box(f"{tag}_rail", (W * 0.5, 0.06, 0.9), (W * 0.22, gy - D / 2 + 0.1, 3.35), M("glass"), c, parent=root)

    # garage on the drive side
    box(f"{tag}_garage", (3.0, 4.2, 2.6), (W / 2 + 1.3, gy + 0.2, 0), M("charcoal"), c, parent=root)
    box(f"{tag}_garage_door", (2.4, 0.1, 2.1), (W / 2 + 1.3, gy + 0.2 - 2.12, 0), M("concrete"), c, parent=root)
    # small yard tree + porch light
    tree(f"{tag}_yardtree", (x - 4.2 if face_south else x + 4.2, y + (2.8 if face_south else -2.8), WALK_H),
         size=0.8, c=coll("Trees"))
    box(f"{tag}_porch", (0.25, 0.12, 0.25), (0.45, gy - D / 2 - 0.08, 2.1), M("lamp"), c, parent=root)


def _win_group(root, w, d, cy, z0, h, c, tag, xoff=0.0, step=1.9):
    g = bpy.data.objects.new(f"{tag}_windows", None)
    c.objects.link(g)
    g.parent = root
    g.location = (xoff, cy, 0)
    windows(g, w + 0.02, d + 0.02, z0, h, c, tag, step)


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
            house(h, x, y, face_south=(y > 0) ^ (abs(y) > 15), style=(h * 7) % 3)
    return h, p


def build_greenery():
    # trees along streets
    i = 0
    for x in range(-62, 63, 7):
        if abs(x) > 6 and random.random() < 0.85:
            tree(f"T_front_{i}", (x + random.uniform(-1, 1), -36.5, 0)); i += 1
    for x in range(-44, 45, 9):
        tree(f"T_lake_{i}", (x + 4, 35.5, WALK_H), kind="leaf_pink" if random.random() < 0.4 else None); i += 1
    for y in range(-26, 27, 8):
        for xx in (-38.5, 38.5):
            tree(f"T_side_{i}", (xx, y, 0)); i += 1
    # plaza blossoms
    for k in range(6):
        a = k * math.pi / 3
        tree(f"T_plaza_{k}", (math.cos(a) * 12.5, math.sin(a) * 12.5 + 0.0, 0), kind="leaf_pink", size=0.9)
    # foreground clusters & meadows
    for k in range(140):
        x = random.uniform(-110, 110)
        y = random.uniform(-110, -38)
        if abs(x) < 7 or abs(y + 30) < 7:
            continue
        kind = "leaf_gold" if random.random() < 0.12 else None
        tree(f"T_meadow_{k}", (x, y, 0), kind=kind, size=random.uniform(0.9, 1.5))
    for k in range(60):
        x = random.choice([random.uniform(-110, -42), random.uniform(42, 110)])
        y = random.uniform(-36, 33)
        tree(f"T_edge_{k}", (x, y, 0), size=random.uniform(0.9, 1.4))
    # hero foreground framing trees (bottom corners of the vertical frame)
    tree("T_hero_L", (-18.5, -45, 0), kind="leaf_gold", size=1.25)
    tree("T_hero_L2", (-19, -52, 0), kind="leaf_pink", size=1.3)


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
        h = random.uniform(8, 18) + center * random.uniform(10, 34)
        y = random.uniform(240, 275)
        box(f"Tower_{k}", (w, d, h), (x, y, -0.9), M("tower_lit"), c)
        if random.random() < 0.35:
            box(f"Tower_{k}_crown", (w * 0.6, d * 0.6, h * 0.15), (x, y, h - 0.9), M("tower_lit"), c)
        if random.random() < 0.3:
            box(f"Tower_{k}_beacon", (0.6, 0.6, 1.5), (x, y, h * 1.15 - 0.9), M("lamp"), c)
        x += w + random.uniform(1, 6)
        k += 1
    # far shore strip
    box("FarShore", (900, 70, 0.6), (0, 262, -0.9), M("grass"), c)
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
    ob.location = Vector((-20, -76, 27))
    target = Vector((6, 8, 9))
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
    s.view_settings.exposure = 0.45
    # cozy bloom on lamps / windows / sun
    s.use_nodes = True
    nt = s.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 1.2
    glare.size = 8
    glare.mix = -0.55
    out = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    nt.links.new(glare.outputs["Image"], out.inputs["Image"])


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
