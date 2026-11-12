"""NO ONE'S CITY — Episode 001 / M0.5: premium modern low-poly district (visual rework).

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


def blob(name, r, loc, material, collection, scale=(1, 1, 1), jitter=0.12, parent=None, subdiv=1):
    """Faceted low-poly crown (jittered icosphere)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0] * (1 + random.uniform(-jitter, jitter))
        v.co.y *= scale[1] * (1 + random.uniform(-jitter, jitter))
        v.co.z *= scale[2] * (1 + random.uniform(-jitter, jitter))
    return mesh_obj(name, bm, material, collection, loc, random.uniform(0, 6.28), parent)


def ring_sector(name, r0, r1, a0, a1, h, loc, material, collection, segs=10, parent=None):
    """Annular sector (r0..r1, angles a0..a1, radians) extruded to height h; pivot at the bottom centre."""
    bm = bmesh.new()
    ib, ob_, it, ot = [], [], [], []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        ca, sa = math.cos(a), math.sin(a)
        ib.append(bm.verts.new((r0 * ca, r0 * sa, 0)))
        ob_.append(bm.verts.new((r1 * ca, r1 * sa, 0)))
        it.append(bm.verts.new((r0 * ca, r0 * sa, h)))
        ot.append(bm.verts.new((r1 * ca, r1 * sa, h)))
    full = abs((a1 - a0) - 2 * math.pi) < 1e-6
    for i in range(segs):
        j = i + 1
        bm.faces.new((it[i], ot[i], ot[j], it[j]))      # top
        bm.faces.new((ib[j], ob_[j], ob_[i], ib[i]))    # bottom
        bm.faces.new((ob_[i], ob_[j], ot[j], ot[i]))    # outer
        bm.faces.new((ib[j], ib[i], it[i], it[j]))      # inner
    if not full:
        bm.faces.new((ib[0], ob_[0], ot[0], it[0]))
        bm.faces.new((it[-1], ot[-1], ob_[-1], ib[-1]))
    else:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, material, collection, loc, 0.0, parent)


def tex_mat(name, c1, c2, mortar, brick_w, row_h, mortar_size=0.01, rough=0.7, facade=False, bias=0.0):
    """Procedural pavers / boards / slats / panels (shader only, no extra geometry).
    facade=True maps the pattern on vertical faces (u = x + y, v = z), else on the ground plane."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Color1"].default_value = (*srgb(c1), 1)
    brick.inputs["Color2"].default_value = (*srgb(c2), 1)
    brick.inputs["Mortar"].default_value = (*srgb(mortar), 1)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = mortar_size
    brick.inputs["Brick Width"].default_value = brick_w
    brick.inputs["Row Height"].default_value = row_h
    brick.inputs["Bias"].default_value = bias
    if facade:
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        add = nt.nodes.new("ShaderNodeMath")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["X"], add.inputs[0])
        nt.links.new(sep.outputs["Y"], add.inputs[1])
        nt.links.new(add.outputs["Value"], comb.inputs["X"])
        nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
        nt.links.new(comb.outputs["Vector"], brick.inputs["Vector"])
    else:
        nt.links.new(tc.outputs["Object"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], b.inputs["Base Color"])
    MATS[name] = m
    return m


# --------------------------------------------------------------------------- palette

def build_materials():
    # ground & street
    mat("grass", "#4c6a33", 0.9)
    mat("grass_lawn", "#5b7d36", 0.85)
    mat("lawn_fine", "#62873a", 0.8)
    mat("asphalt", "#373d4c", 0.75)
    mat("asphalt_x", "#3f4556", 0.72)
    mat("curb", "#d6ccbc", 0.7)
    mat("marking", "#ece3cf", 0.6)
    mat("line_white", "#e6e1d6", 0.6)
    tex_mat("sidewalk", "#c3b7a5", "#b6a994", "#8e8272", 0.6, 0.3, 0.012, 0.75)
    tex_mat("plaza", "#ddcdb2", "#cfbd9f", "#9d8b72", 0.9, 0.45, 0.01, 0.65)
    mat("plaza_dark", "#7d6c58", 0.7)
    mat("paving_ring", "#a99173", 0.7)
    tex_mat("deck", "#8f5d3b", "#7f5032", "#3b2416", 2.4, 0.16, 0.012, 0.7)
    mat("gold_glow", "#f5b04a", 0.4, emit="#ffb347", strength=6.0)
    mat("bollard", "#ffd9a0", 0.3, emit="#ffbf6a", strength=10.0)
    mat("rail_glow", "#ffcf80", 0.3, emit="#ffb85c", strength=8.0)
    mat("led_warm", "#ffd39a", 0.3, emit="#ffbe72", strength=7.0)
    mat("water", "#14284a", 0.03, spec=0.9)
    mat("fountain_water", "#1d5880", 0.03, emit="#5ab4e6", strength=0.35)
    # greenery (greens only)
    mat("trunk", "#5b4130", 0.9)
    for i, c in enumerate(["#3f6f35", "#4f7f3a", "#5e8f43", "#365f2e", "#6b9a4a"]):
        mat(f"leaf_{i}", c, 0.8)
    mat("shrub", "#4c7a39", 0.9)
    mat("shrub_dark", "#355d2e", 0.9)
    mat("hedge", "#3b6430", 0.9)
    mat("soil", "#4a3426", 0.95)
    for n, c in (("white", "#f6f1e6"), ("yellow", "#f2cf55"), ("lavender", "#9b92e0")):
        mat(f"flower_{n}", c, 0.7)
    # architecture: warm wood, graphite, concrete, glass, neutral render
    for n, c in (("white", "#f1ede6"), ("sand", "#dcccb0"), ("grey", "#c6c7c8"), ("cream", "#ece3d1")):
        mat(f"wall_{n}", c, 0.7)
    mat("render_white", "#eeeae3", 0.75)
    tex_mat("concrete_light", "#c3bdb3", "#bbb4a9", "#9f978b", 1.2, 0.6, 0.006, 0.8, facade=True)
    mat("graphite", "#30333a", 0.55)
    mat("clad_dark", "#383b44", 0.6)
    tex_mat("clad_wood", "#b07648", "#9a6239", "#4a2c18", 0.16, 30.0, 0.025, 0.6, facade=True)
    mat("roof_metal", "#474b55", 0.45, metallic=0.3)
    mat("mullion", "#24262c", 0.45)
    mat("steel", "#5c6068", 0.35, metallic=0.6)
    mat("wood", "#9a6440", 0.6)
    mat("charcoal", "#2c2f38", 0.6)
    mat("roof", "#363941", 0.7)
    mat("window", "#ffb860", 0.2, emit="#ffa94d", strength=3.0)
    mat("window_soft", "#ffd6a0", 0.2, emit="#ffc98a", strength=1.9)
    mat("window_pano", "#ffb46a", 0.2, emit="#ffa452", strength=1.5)   # large glazing: warm, not clipped
    mat("glass", "#86a6c4", 0.08, spec=0.9)
    mat("glass_dark", "#1d2b3d", 0.05, spec=0.9)
    mat("concrete", "#a39c92", 0.8)
    mat("dirt", "#a8916f", 0.95)
    mat("lamp", "#ffd9a0", 0.3, emit="#ffc977", strength=16.0)
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
    """Promenade, slatted boardwalk with glass railing, amphitheatre steps to the water,
    lookout pier with a pavilion and a round viewing deck."""
    c = coll("Waterfront")
    steps_x = (12.0, 28.0)          # amphitheatre steps down to the water
    pier_x = (-11.5, -6.5)          # pier entrance

    def spans(lo, hi, holes):
        return _segments(lo, hi, [((a + b) / 2, b - a) for a, b in holes])

    box("Promenade", (700, 2.6, WALK_H), (0, 37.5, 0), M("sidewalk"), c)           # y 36.2..38.8
    box("Boardwalk", (700, 3.4, WALK_H + 0.04), (0, 40.5, 0), M("deck"), c)        # y 38.8..42.2
    box("Boardwalk_Edge", (700, 0.25, WALK_H + 0.06), (0, 38.9, 0), M("curb"), c)  # stone edge between the two
    for k, (a, b) in enumerate(spans(-350, 350, [steps_x])):
        box(f"Quay_Wall_{k}", (b - a, 0.8, 1.15), ((a + b) / 2, 42.6, -0.95), M("concrete"), c)
        box(f"Quay_Step_{k}", (b - a, 1.2, 0.5), ((a + b) / 2, 43.4, -0.95), M("concrete"), c)
    # glass railing with steel posts + warm LED strip at deck level
    for k, (a, b) in enumerate(spans(-108, 108, [steps_x, pier_x])):
        box(f"Rail_Top_{k}", (b - a, 0.08, 0.06), ((a + b) / 2, 42.0, 1.17), M("steel"), c)
        box(f"Rail_LED_{k}", (b - a, 0.06, 0.04), ((a + b) / 2, 42.12, WALK_H + 0.04), M("led_warm"), c)
        n = max(1, int((b - a) // 3))
        for i in range(n):
            x0 = a + i * (b - a) / n
            box(f"Rail_Glass_{k}_{i}", ((b - a) / n - 0.1, 0.03, 0.9), (x0 + (b - a) / n / 2, 42.0, WALK_H + 0.27), M("glass"), c)
            box(f"Rail_Post_{k}_{i}", (0.07, 0.07, 1.0), (x0, 42.0, WALK_H + 0.04), M("steel"), c)
    # amphitheatre steps (seating) down to a landing at the water line
    sx0, sx1 = steps_x
    for k in range(3):
        top = WALK_H + 0.04 - (k + 1) * 0.3
        y0 = 42.2 + k * 0.95
        box(f"Steps_{k}", (sx1 - sx0, 0.95, top + 0.95), ((sx0 + sx1) / 2, y0 + 0.475, -0.95), M("concrete_light"), c)
        if k == 1:
            for j in range(4):
                box(f"Steps_Seat_{j}", (2.6, 0.6, 0.06), (sx0 + 2.5 + j * 3.7, y0 + 0.45, top), M("deck"), c)
    box("Steps_Landing", (sx1 - sx0, 1.6, 0.25), ((sx0 + sx1) / 2, 45.85 + 0.8, -0.95), M("concrete_light"), c)
    for xx in (sx0 + 0.3, sx1 - 0.3):
        box(f"Steps_Cheek_{xx:.0f}", (0.5, 4.6, 1.15), (xx, 44.5, -0.95), M("concrete"), c)
        box(f"Steps_CheekLED_{xx:.0f}", (0.06, 3.6, 0.04), (xx + (0.27 if xx < 20 else -0.27), 44.3, 0.18), M("led_warm"), c)
    # mooring bollards on the quay
    for i, x in enumerate(range(-100, 101, 12)):
        if sx0 - 1 < x < sx1 + 1 or pier_x[0] - 1 < x < pier_x[1] + 1:
            continue
        cyl(f"Mooring_{i}", 0.2, 0.16, 0.5, 8, (x, 43.4, -0.45), M("graphite"), c)
    # planters with green trees + modern benches facing the lake
    for i, x in enumerate(range(-45, 46, 10)):
        if abs(x) < 6:
            continue
        box(f"Planter_{i}", (2.6, 1.4, 0.55), (x, 37.4, WALK_H), M("concrete_light"), c)
        box(f"Planter_{i}_soil", (2.4, 1.2, 0.05), (x, 37.4, WALK_H + 0.52), M("soil"), c)
        tree(f"Prom_Tree_{i}", (x, 37.4, WALK_H + 0.55), shape="round", size=0.8)
        for k in range(3):
            shrub(f"Planter_{i}_sh{k}", (x - 0.8 + k * 0.8, 36.9, WALK_H + 0.55), 0.32)
        bench(f"Prom_Bench_{i}", (x + 4.5, 40.3, WALK_H + 0.04), 0.0, c)
    # lookout pier: slatted deck, glass rails, lamps, pavilion and a round viewing deck
    px = -9
    box("Pier", (5, 22, 0.35), (px, 53, -0.2), M("deck"), c)
    for k in range(6):
        for sx in (-1, 1):
            cyl(f"Pier_Pile_{k}_{sx}", 0.18, 0.18, 1.2, 6, (px + sx * 2.2, 44 + k * 4, -1.0), M("charcoal"), c)
    for sx in (-1, 1):
        box(f"Pier_RailGlass_{sx}", (0.03, 15.5, 0.9), (px + sx * 2.45, 50.5, 0.42), M("glass"), c)
        box(f"Pier_RailTop_{sx}", (0.08, 15.5, 0.06), (px + sx * 2.45, 50.5, 1.32), M("steel"), c)
        box(f"Pier_LED_{sx}", (0.06, 15.5, 0.04), (px + sx * 2.35, 50.5, 0.17), M("led_warm"), c)
    for k in range(4):
        box(f"Pier_Light_{k}", (0.16, 0.16, 0.8), (px + 2.2, 45 + k * 4.5, 0.15), M("bollard"), c)
        box(f"Pier_LightL_{k}", (0.16, 0.16, 0.8), (px - 2.2, 45 + k * 4.5, 0.15), M("bollard"), c)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"Pavilion_Post_{sx}_{sy}", (0.12, 0.12, 2.8), (px + sx * 2.1, 61 + sy * 2.1, 0.15), M("steel"), c)
    box("Pavilion_Roof", (6.0, 6.0, 0.22), (px, 61, 2.95), M("graphite"), c)
    box("Pavilion_Soffit", (5.8, 5.8, 0.04), (px, 61, 2.92), M("clad_wood"), c)
    for sy in (-1, 1):
        box(f"Pavilion_Cove_{sy}", (5.8, 0.08, 0.05), (px, 61 + sy * 2.95, 2.9), M("led_warm"), c)
    bench("Pavilion_Bench", (px, 62.2, 0.15), math.pi, c)
    point_light("Pavilion_Light", (px, 61, 2.5), energy=160, radius=0.8)
    cyl("Lookout_Deck", 4.2, 4.2, 0.35, 20, (px, 67, -0.2), M("deck"), c)
    ring_sector("Lookout_Rail", 4.0, 4.06, math.radians(200), math.radians(340 + 360), 0.9, (px, 67, 0.15), M("glass"), c, segs=20)
    ring_sector("Lookout_RailTop", 3.98, 4.08, math.radians(200), math.radians(340 + 360), 0.06, (px, 67, 1.05), M("steel"), c, segs=20)
    ring_sector("Lookout_LED", 4.12, 4.2, 0, 2 * math.pi, 0.04, (px, 67, 0.12), M("led_warm"), c, segs=24)


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
        ce = width / 2 + 0.11 - 0.02      # curb protrudes 2 cm into the road: no coplanar faces
        le = width / 2 - 0.35             # edge line
        for side in (-1, 1):
            if along_x:
                box(f"{name}_walk{k}_{side}", (ln, 2.2, WALK_H), (mid, loc[1] + side * off, 0), M("sidewalk"), c)
                box(f"{name}_curb{k}_{side}", (ln, 0.22, WALK_H + 0.03), (mid, loc[1] + side * ce, 0), M("curb"), c)
                box(f"{name}_edge{k}_{side}", (ln - 1.0, 0.12, 0.01), (mid, loc[1] + side * le, ROAD_Z), M("line_white"), c)
            else:
                box(f"{name}_walk{k}_{side}", (2.2, ln, WALK_H), (loc[0] + side * off, mid, 0), M("sidewalk"), c)
                box(f"{name}_curb{k}_{side}", (0.22, ln, WALK_H + 0.03), (loc[0] + side * ce, mid, 0), M("curb"), c)
                box(f"{name}_edge{k}_{side}", (0.12, ln - 1.0, 0.01), (loc[0] + side * le, mid, ROAD_Z), M("line_white"), c)
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
    # parallel parking bays along the south side of Front Street
    for side in (-1, 1):
        for k in range(5):
            x = side * (9.0 + k * 5.5)
            box(f"Parking_{side}_{k}", (0.12, 2.2, 0.01), (x, -32.4, ROAD_Z + 0.003), M("line_white"), c)
        box(f"Parking_{side}_end", (0.12, 2.2, 0.01), (side * (9.0 + 5 * 5.5), -32.4, ROAD_Z + 0.003), M("line_white"), c)
    junction("Junction_Lake", 0, 31, 8, 6, c, zebras="s")
    for x in (-34, 34):
        junction(f"Junction_{x}_front", x, -30, 7, 7, c, zebras="n")
        junction(f"Junction_{x}_cross", x, 0, 7, 7, c)
        junction(f"Junction_{x}_lake", x, 31, 7, 6, c)


def bench(name, loc, rot_z, c, length=1.9):
    """Modern bench: slatted wooden seat on two graphite legs."""
    x, y, z = loc
    root = bpy.data.objects.new(name, None)
    c.objects.link(root)
    root.location = (x, y, z)
    root.rotation_euler.z = rot_z
    box(f"{name}_seat", (length, 0.5, 0.08), (0, 0, 0.42), M("deck"), c, parent=root)
    box(f"{name}_back", (length, 0.06, 0.38), (0, 0.24, 0.5), M("deck"), c, parent=root)
    for sx in (-1, 1):
        box(f"{name}_leg{sx}", (0.08, 0.5, 0.42), (sx * (length / 2 - 0.2), 0, 0), M("graphite"), c, parent=root)
    return root


def build_plaza():
    c = coll("Plaza")
    # paving: stone base, large pavers, darker band and radial joints
    cyl("Plaza_Base", 10.6, 10.6, 0.24, 48, (0, 0, 0), M("plaza_dark"), c)
    cyl("Plaza_Top", 10.2, 10.2, 0.27, 48, (0, 0, 0), M("plaza"), c)
    ring_sector("Plaza_Band", 9.2, 9.7, 0, 2 * math.pi, 0.28, (0, 0, 0), M("paving_ring"), c, segs=48)
    ring_sector("Plaza_InnerBand", 4.6, 5.0, 0, 2 * math.pi, 0.28, (0, 0, 0), M("paving_ring"), c, segs=40)
    for i in range(24):
        a = i * math.pi / 12
        box(f"Plaza_Joint_{i}", (0.6, 0.06, 0.01), (math.cos(a) * 9.95, math.sin(a) * 9.95, 0.27), M("plaza_dark"), c, rot_z=a)
    # four green islands on the diagonals with integrated wooden seating and LED under the seat
    for i in range(4):
        ac = i * math.pi / 2 + math.pi / 4
        a0, a1 = ac - math.radians(30), ac + math.radians(30)
        ring_sector(f"Island_{i}_wall", 6.6, 9.0, a0, a1, 0.55, (0, 0, 0.27), M("concrete_light"), c)
        ring_sector(f"Island_{i}_lawn", 6.8, 8.8, a0 + 0.03, a1 - 0.03, 0.6, (0, 0, 0.27), M("lawn_fine"), c)
        ring_sector(f"Island_{i}_seat", 6.5, 6.95, a0 + 0.02, a1 - 0.02, 0.07, (0, 0, 0.82), M("deck"), c)
        ring_sector(f"Island_{i}_led", 6.55, 6.6, a0 + 0.04, a1 - 0.04, 0.04, (0, 0, 0.32), M("led_warm"), c)
        tx, ty = math.cos(ac) * 7.9, math.sin(ac) * 7.9
        tree(f"Plaza_Tree_{i}", (tx, ty, 0.87), shape="round", size=0.95)
        for k, da in enumerate((-0.38, -0.2, 0.2, 0.38)):
            r = 7.6 if k % 2 else 8.2
            shrub(f"Island_{i}_sh{k}", (math.cos(ac + da) * r, math.sin(ac + da) * r, 0.87), 0.38)
        for k, da in enumerate((-0.42, 0.42)):
            cyl(f"Island_{i}_uplight{k}", 0.1, 0.1, 0.12, 8, (math.cos(ac + da) * 8.5, math.sin(ac + da) * 8.5, 0.87), M("bollard"), c)
    # modern fountain: wide basin with LED rim, central plinth and a crown of jets
    ring_sector("Fountain_Rim", 3.9, 4.25, 0, 2 * math.pi, 0.6, (0, 0, 0.27), M("concrete_light"), c, segs=40)
    cyl("Fountain_Water", 3.92, 3.92, 0.5, 40, (0, 0, 0.27), M("fountain_water"), c)
    ring_sector("Fountain_RimLED", 3.92, 4.0, 0, 2 * math.pi, 0.03, (0, 0, 0.86), M("led_warm"), c, segs=40)
    ring_sector("Fountain_RimCap", 4.0, 4.3, 0, 2 * math.pi, 0.06, (0, 0, 0.84), M("plaza"), c, segs=40)
    cyl("Fountain_Plinth", 1.2, 1.0, 0.55, 16, (0, 0, 0.27), M("concrete_light"), c)
    cyl("Fountain_PlinthWater", 0.95, 0.95, 0.57, 16, (0, 0, 0.27), M("fountain_water"), c)
    cyl("Fountain_Jet", 0.2, 0.03, 3.0, 8, (0, 0, 0.82), M("fountain_water"), c)
    for i in range(8):
        a = i * math.pi / 4
        cyl(f"Fountain_Jet_{i}", 0.09, 0.02, 1.1 + 0.25 * (i % 2), 6, (math.cos(a) * 2.5, math.sin(a) * 2.5, 0.77), M("fountain_water"), c)
    point_light("Fountain_Glow", (0, 0, 1.6), "#8fd0ff", 300, 1.0)
    # white & yellow flowers and a low clipped hedge ring around the basin
    ring_sector("Fountain_Hedge", 4.35, 4.6, 0, 2 * math.pi, 0.45, (0, 0, 0.27), M("hedge"), c, segs=32)
    # freestanding benches facing the fountain
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        bench(f"Bench_{i}", (math.cos(a) * 5.6, math.sin(a) * 5.6, 0.27), a - math.pi / 2, c)
    # light: bollards on the outer band and four modern lamps
    for i in range(16):
        a = i * math.pi / 8 + math.pi / 16
        cyl(f"Bollard_{i}", 0.08, 0.08, 0.45, 8, (math.cos(a) * 9.45, math.sin(a) * 9.45, 0.27), M("bollard"), c)
    for i, a in enumerate((math.pi / 4 + 0.32, 3 * math.pi / 4 + 0.32, 5 * math.pi / 4 + 0.32, -1.0)):
        lamp(f"PlazaLamp_{i}", (math.cos(a) * 9.9, math.sin(a) * 9.9, 0.27), light=True)


def lamp(name, loc, light=False):
    """Modern street light: concrete footing, slim graphite pole, flat disc luminaire."""
    c = coll("Lamps")
    x, y, z = loc
    cyl(f"{name}_base", 0.2, 0.17, 0.35, 8, (x, y, z), M("concrete_light"), c)
    cyl(f"{name}_pole", 0.07, 0.055, 4.6, 8, (x, y, z + 0.35), M("graphite"), c)
    cyl(f"{name}_cap", 0.4, 0.33, 0.1, 16, (x, y, z + 4.95), M("graphite"), c)
    cyl(f"{name}_head", 0.34, 0.34, 0.03, 16, (x, y, z + 4.93), M("lamp"), c)
    if light:
        point_light(f"{name}_light", (x, y, z + 4.6), energy=220, radius=0.4)


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


TREE_GREENS = ["leaf_0", "leaf_1", "leaf_2", "leaf_3", "leaf_4"]


def tree(name, loc, kind=None, size=1.0, c=None, shape=None):
    """Clean modern street tree: smooth low-poly crown in one of five greens.
    shapes: round (lime / maple), columnar (hornbeam / poplar), layered (two-tier crown)."""
    c = c or coll("Trees")
    x, y, z = loc
    kind = kind if kind in TREE_GREENS else random.choice(TREE_GREENS)
    shape = shape or random.choices(["round", "columnar", "layered"], weights=[6, 2, 2])[0]
    h = random.uniform(1.8, 2.3) * size
    cyl(f"{name}_trunk", 0.15 * size, 0.1 * size, h + 0.6 * size, 7, (x, y, z), M("trunk"), c)
    if shape == "columnar":
        r = 0.85 * size
        blob(f"{name}_crown", r, (x, y, z + h + r * 2.0), M(kind), c, scale=(1, 1, 2.4), jitter=0.04, subdiv=2)
    elif shape == "layered":
        r = 1.45 * size
        blob(f"{name}_crown", r, (x, y, z + h + r * 0.55), M(kind), c, scale=(1, 1, 0.72), jitter=0.05, subdiv=2)
        blob(f"{name}_crown2", r * 0.68, (x, y, z + h + r * 1.35), M(kind), c, scale=(1, 1, 0.8), jitter=0.05, subdiv=2)
    else:
        r = random.uniform(1.35, 1.7) * size
        blob(f"{name}_crown", r, (x, y, z + h + r * 0.7), M(kind), c, scale=(1, 1, 0.92), jitter=0.05, subdiv=2)


def cherry(name, loc, size=1.0, c=None):
    """Kept for compatibility with older scripts: now a small green ornamental tree (no pink blossom)."""
    return tree(name, loc, size=size * 0.85, c=c, shape="round")


def shrub(name, loc, r=0.5, c=None):
    c = c or coll("Trees")
    return blob(name, r, (loc[0], loc[1], loc[2] + r * 0.5), M(random.choice(["shrub", "shrub_dark", "leaf_1"])), c,
                scale=(1.1, 1.1, 0.8), jitter=0.06, subdiv=2)


def flowerbed(name, loc, w, d, c, rot_z=0.0, parent=None):
    """Raised soil bed with a few low-poly flower clusters (local to `parent` when given)."""
    box(f"{name}_edge", (w, d, 0.28), loc, M("curb"), c, rot_z=rot_z, parent=parent)
    box(f"{name}_soil", (w - 0.2, d - 0.2, 0.3), loc, M("soil"), c, rot_z=rot_z, parent=parent)
    colors = ["flower_white", "flower_white", "flower_yellow", "flower_lavender"]
    n = max(3, int(w * d * 1.4))
    for i in range(n):
        fx = loc[0] + random.uniform(-w / 2 + 0.25, w / 2 - 0.25)
        fy = loc[1] + random.uniform(-d / 2 + 0.25, d / 2 - 0.25)
        b = blob(f"{name}_f{i}", 0.2, (fx, fy, loc[2] + 0.38), M(random.choice(colors)), c, scale=(1, 1, 0.8))
        if parent:
            b.parent = parent


# --------------------------------------------------------------------------- houses & plots

PALETTES = [  # (main volume, accent volume)
    ("render_white", "clad_wood"), ("concrete_light", "clad_wood"), ("graphite", "clad_wood"),
    ("render_white", "graphite"), ("concrete_light", "graphite"), ("render_white", "concrete_light"),
]
STYLE_NAMES = ["cantilever", "courtyard", "pavilion", "split", "gable"]
LIT_RATIO = 0.75   # share of glazing that glows; the rest reads as dark reflective glass


def _pane_mat(large=False):
    if random.random() < LIT_RATIO:
        if large:
            return M("window_pano")
        return M("window") if random.random() < 0.7 else M("window_soft")
    return M("glass_dark")


def windows(parent, w, d, z0, h, c, tag, step=1.9, front=True):
    """Window panes with thin frames on the facades of a w x d volume (front = -Y)."""
    n = max(1, int(w // step))
    for i in range(n):
        x = -w / 2 + (i + 0.5) * w / n
        for side in ((-1, 1) if front else (1,)):
            if random.random() < 0.15:
                continue
            box(f"{tag}_win_{i}_{side}", (w / n * 0.62, 0.08, h), (x, side * d / 2, z0), _pane_mat(), c, parent=parent)
            box(f"{tag}_winf_{i}_{side}", (w / n * 0.62 + 0.1, 0.1, 0.07), (x, side * d / 2, z0 + h), M("mullion"), c, parent=parent)
    nd = max(1, int(d // step))
    for i in range(nd):
        y = -d / 2 + (i + 0.5) * d / nd
        for side in (-1, 1):
            if random.random() < 0.35:
                continue
            box(f"{tag}_swin_{i}_{side}", (0.08, d / nd * 0.55, h), (side * w / 2, y, z0), _pane_mat(), c, parent=parent)


def _win_group(root, w, d, cy, z0, h, c, tag, xoff=0.0, step=1.9, front=True):
    g = bpy.data.objects.new(f"{tag}_windows", None)
    c.objects.link(g)
    g.parent = root
    g.location = (xoff, cy, 0)
    windows(g, w + 0.02, d + 0.02, z0, h, c, tag, step, front)


def panoramic(root, tag, c, x, yf, z0, w, h, n=3):
    """Floor-to-ceiling glazing in a slim graphite frame (front facing -Y), mixed lit / dark panes."""
    for i in range(n):
        px = x - w / 2 + (i + 0.5) * w / n
        box(f"{tag}_pane{i}", (w / n, 0.06, h), (px, yf - 0.03, z0), _pane_mat(large=True), c, parent=root)
    for i in range(n + 1):
        mx = x - w / 2 + i * w / n
        box(f"{tag}_mull{i}", (0.06, 0.12, h), (mx, yf - 0.06, z0), M("mullion"), c, parent=root)
    box(f"{tag}_head", (w + 0.12, 0.16, 0.09), (x, yf - 0.07, z0 + h - 0.04), M("mullion"), c, parent=root)
    box(f"{tag}_sill", (w + 0.12, 0.18, 0.06), (x, yf - 0.07, z0), M("mullion"), c, parent=root)


def balcony(root, tag, c, x, yf, z, w, depth=1.2):
    box(f"{tag}_slab", (w, depth, 0.16), (x, yf - depth / 2, z), M("graphite"), c, parent=root)
    box(f"{tag}_soffitLED", (w - 0.3, 0.06, 0.03), (x, yf - depth + 0.15, z - 0.03), M("led_warm"), c, parent=root)
    box(f"{tag}_rail", (w, 0.04, 0.95), (x, yf - depth + 0.03, z + 0.16), M("glass"), c, parent=root)
    box(f"{tag}_handrail", (w, 0.07, 0.05), (x, yf - depth + 0.03, z + 1.11), M("steel"), c, parent=root)
    for sx in (-1, 1):
        box(f"{tag}_rail_s{sx}", (0.04, depth, 0.95), (x + sx * w / 2, yf - depth / 2, z + 0.16), M("glass"), c, parent=root)


def fins(root, tag, c, x0, x1, yf, z0, h, n=5):
    for i in range(n):
        fx = x0 + (i + 0.5) * (x1 - x0) / n
        box(f"{tag}_fin{i}", (0.1, 0.35, h), (fx, yf - 0.17, z0), M("clad_wood"), c, parent=root)


def roof_slab(root, tag, c, x, y, z, w, d, led_front=None):
    """Thin floating roof with a graphite fascia; optional warm LED cove under the front edge (y = led_front)."""
    box(f"{tag}", (w, d, 0.2), (x, y, z), M("graphite"), c, parent=root)
    if led_front is not None:
        box(f"{tag}_cove", (w - 0.4, 0.07, 0.04), (x, led_front + 0.25, z - 0.04), M("led_warm"), c, parent=root)


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


def gable_roof(tag, c, root, x, cy, w, d, hw, hr, material="roof_metal", extra=0.7):
    slope = math.atan2(hr, w / 2)
    ln = math.hypot(w / 2, hr) + 0.45
    for sx in (-1, 1):
        r = box(f"{tag}_roof{sx}", (ln, d + extra, 0.18), (x + sx * w / 4, cy, hw + hr / 2 + 0.04), M(material), c, parent=root)
        r.rotation_euler.y = slope if sx > 0 else -slope


def lot_landscape(root, tag, c, W, D, gy):
    """Lawn, pavers, stepping-stone entry path with garden lights, clipped hedges, shrubs."""
    box(f"{tag}_lawn", (10.2, 8.4, 0.06), (0, 0, -0.04), M("lawn_fine"), c, parent=root)
    box(f"{tag}_drive", (2.9, 2.9, 0.08), (3.95, -2.75, -0.04), M("sidewalk"), c, parent=root)
    for k in range(3):
        box(f"{tag}_step{k}", (1.3, 0.55, 0.08), (-0.6, -3.75 + k * 0.62, -0.03), M("concrete_light"), c, parent=root)
    for k, sx in enumerate((-1.45, 0.25)):
        cyl(f"{tag}_gardenlight{k}", 0.07, 0.07, 0.45, 8, (sx, -3.4, 0.0), M("bollard"), c, parent=root)
    box(f"{tag}_hedge_front", (3.4, 0.45, 0.55), (-3.4, -3.95, 0), M("hedge"), c, parent=root)
    box(f"{tag}_hedge_back", (10.0, 0.5, 0.9), (0, 3.95, 0), M("hedge"), c, parent=root)
    flowerbed(f"{tag}_bed", (-3.3, -3.2, 0), 2.8, 0.7, c, parent=root)
    for k, (sx, sy) in enumerate(((-4.6, -1.6), (-4.6, 0.4), (4.7, 3.2))):
        sh = shrub(f"{tag}_shrub{k}", (sx, sy, 0), 0.45, c)
        sh.parent = root


def house(idx, x, y, face_south, style):
    c = coll("Houses")
    tag = f"House_{idx:02d}_{STYLE_NAMES[style]}"
    root = bpy.data.objects.new(tag, None)
    c.objects.link(root)
    root.location = (x, y, WALK_H)
    root.rotation_euler.z = 0 if face_south else math.pi
    main_name, accent_name = PALETTES[idx % len(PALETTES)]
    main, accent = M(main_name), M(accent_name)
    lot_landscape(root, tag, c, 0, 0, 0)

    W = random.uniform(7.0, 7.6)
    D = random.uniform(5.0, 5.5)
    gy = 0.6
    yf = gy - D / 2
    garage = True
    door_x = -W / 2 + 1.0
    box(f"{tag}_plinth", (W + 0.5, D + 0.5, 0.2), (0, gy, 0), M("concrete_light"), c, parent=root)
    Z0 = 0.2

    if style == 0:      # cantilever villa: glazed ground floor, timber/graphite box cantilevered over a terrace
        box(f"{tag}_ground", (W, D - 0.4, 3.0), (0, gy + 0.2, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, 0.4, yf + 0.4, Z0 + 0.1, W * 0.74, 2.6, 4)
        _win_group(root, W, D - 0.4, gy + 0.2, Z0 + 0.5, 1.9, c, f"{tag}_g", front=False)
        uw, ud = W + 0.4, D + 1.4
        uy = gy - 0.7
        box(f"{tag}_upper", (uw, ud, 2.8), (0.2, uy, Z0 + 3.0), accent, c, parent=root)
        panoramic(root, f"{tag}_upano", c, 0.0, uy - ud / 2, Z0 + 3.35, uw * 0.78, 1.9, 4)
        _win_group(root, uw, ud, uy, Z0 + 3.6, 1.6, c, f"{tag}_u", xoff=0.2, front=False)
        roof_slab(root, f"{tag}_roof", c, 0.2, uy, Z0 + 5.8, uw + 0.5, ud + 0.5)
        box(f"{tag}_soffitLED", (uw - 0.4, 0.07, 0.04), (0.2, uy - ud / 2 + 0.2, Z0 + 2.96), M("led_warm"), c, parent=root)
        box(f"{tag}_terrace", (W, 1.5, 0.12), (0, yf - 0.55, 0.0), M("deck"), c, parent=root)
    elif style == 1:    # courtyard L: two-storey timber block + single-storey wing with a roof terrace
        bw, bx = W * 0.5, -W * 0.25
        box(f"{tag}_block", (bw, D, 5.9), (bx, gy, Z0), accent, c, parent=root)
        panoramic(root, f"{tag}_bpano", c, bx + 0.25, yf, Z0 + 0.15, bw * 0.6, 5.4, 2)
        box(f"{tag}_floorband", (bw * 0.6 + 0.12, 0.2, 0.18), (bx + 0.25, yf - 0.08, Z0 + 2.85), M("mullion"), c, parent=root)
        _win_group(root, bw, D, gy, Z0 + 0.5, 1.9, c, f"{tag}_g", xoff=bx, front=False)
        _win_group(root, bw, D, gy, Z0 + 3.5, 1.7, c, f"{tag}_u", xoff=bx, front=False)
        roof_slab(root, f"{tag}_roof", c, bx, gy, Z0 + 5.9, bw + 0.5, D + 0.5)
        ww, wx = W * 0.52, W * 0.24
        wd = D * 0.8
        box(f"{tag}_wing", (ww, wd, 3.0), (wx, gy + D * 0.1, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_wpano", c, wx, gy + D * 0.1 - wd / 2, Z0 + 0.15, ww * 0.8, 2.6, 3)
        roof_slab(root, f"{tag}_wroof", c, wx, gy + D * 0.1, Z0 + 3.0, ww + 0.3, wd + 0.3, led_front=gy + D * 0.1 - wd / 2 - 0.15)
        box(f"{tag}_wrail", (ww, 0.04, 0.9), (wx, gy + D * 0.1 - wd / 2 + 0.05, Z0 + 3.2), M("glass"), c, parent=root)
        box(f"{tag}_planter", (ww * 0.7, 0.5, 0.4), (wx, gy + D * 0.1 + wd / 2 - 0.5, Z0 + 3.2), M("graphite"), c, parent=root)
        for k in range(3):
            sh = shrub(f"{tag}_roofsh{k}", (wx - 0.9 + k * 0.9, gy + D * 0.1 + wd / 2 - 0.5, Z0 + 3.6), 0.35, c)
            sh.parent = root
        box(f"{tag}_court", (ww, 1.2, 0.12), (wx, gy + D * 0.1 - wd / 2 - 0.6, 0.0), M("deck"), c, parent=root)
        door_x = bx - bw / 2 + 0.75
    elif style == 2:    # pavilion: long glass box under a floating roof with LED cove and a timber feature wall
        bw = W * 0.92
        box(f"{tag}_body", (bw, D - 0.3, 3.1), (0, gy + 0.15, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, 0.3, yf + 0.3, Z0 + 0.05, bw * 0.82, 2.9, 5)
        _win_group(root, bw, D - 0.3, gy + 0.15, Z0 + 0.4, 2.3, c, f"{tag}_g", front=False, step=1.6)
        rw, rd = bw + 1.8, D + 2.2
        roof_slab(root, f"{tag}_roof", c, 0.2, gy - 0.5, Z0 + 3.1, rw, rd, led_front=gy - 0.5 - rd / 2)
        for sx in (-1, 1):
            box(f"{tag}_cove_s{sx}", (0.07, rd - 0.6, 0.04), (0.2 + sx * (rw / 2 - 0.25), gy - 0.5, Z0 + 3.06), M("led_warm"), c, parent=root)
            box(f"{tag}_col{sx}", (0.1, 0.1, 3.1), (0.2 + sx * (rw / 2 - 0.35), gy - 0.5 - rd / 2 + 0.35, Z0), M("steel"), c, parent=root)
        box(f"{tag}_featurewall", (0.35, D + 1.0, 3.1), (-bw / 2 - 0.1, gy - 0.3, Z0), M("clad_wood"), c, parent=root)
        box(f"{tag}_terrace", (bw, 1.6, 0.12), (0.1, yf - 0.6, 0.0), M("deck"), c, parent=root)
        box(f"{tag}_roofbox", (bw * 0.35, D * 0.5, 1.6), (-bw * 0.18, gy + 0.6, Z0 + 3.3), accent, c, parent=root)
        panoramic(root, f"{tag}_rpano", c, -bw * 0.18, gy + 0.6 - D * 0.25, Z0 + 3.45, bw * 0.3, 1.2, 2)
        roof_slab(root, f"{tag}_roof2", c, -bw * 0.18, gy + 0.6, Z0 + 4.9, bw * 0.35 + 0.4, D * 0.5 + 0.4)
        door_x = bw / 2 - 0.9
        garage = False
    elif style == 3:    # split level: stepped volumes, terraces on each step, cantilevered timber box
        v1w, v1x = W * 0.5, -W * 0.25
        box(f"{tag}_v1", (v1w, D * 0.62, 3.0), (v1x, gy - D * 0.19, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_v1pano", c, v1x, yf, Z0 + 0.1, v1w * 0.8, 2.6, 3)
        box(f"{tag}_v1rail", (v1w, 0.04, 0.9), (v1x, yf + 0.05, Z0 + 3.2), M("glass"), c, parent=root)
        roof_slab(root, f"{tag}_v1roof", c, v1x, gy - D * 0.19, Z0 + 3.0, v1w + 0.2, D * 0.62 + 0.2)
        box(f"{tag}_v2", (W, D * 0.42, 6.2), (0, gy + D * 0.29, Z0), M("concrete_light") if main_name != "concrete_light" else M("render_white"), c, parent=root)
        panoramic(root, f"{tag}_v2pano", c, v1x, gy + D * 0.08, Z0 + 3.35, v1w * 0.8, 2.4, 3)
        _win_group(root, W, D * 0.42, gy + D * 0.29, Z0 + 3.6, 1.7, c, f"{tag}_v2", front=False)
        roof_slab(root, f"{tag}_v2roof", c, 0, gy + D * 0.29, Z0 + 6.2, W + 0.4, D * 0.42 + 0.4)
        v3w, v3x = W * 0.5, W * 0.25
        box(f"{tag}_v3", (v3w, D * 0.75, 2.7), (v3x, gy - D * 0.1, Z0 + 3.0), M("clad_wood"), c, parent=root)
        panoramic(root, f"{tag}_v3pano", c, v3x, gy - D * 0.1 - D * 0.375, Z0 + 3.3, v3w * 0.75, 1.9, 2)
        box(f"{tag}_v3soffit", (v3w - 0.3, 0.07, 0.04), (v3x, gy - D * 0.1 - D * 0.375 + 0.2, Z0 + 2.96), M("led_warm"), c, parent=root)
        box(f"{tag}_carport_wall", (v3w, D * 0.75, 3.0), (v3x, gy - D * 0.1 + D * 0.3, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_gpano", c, v3x, gy - D * 0.1 + D * 0.3 - D * 0.375, Z0 + 0.1, v3w * 0.7, 2.5, 2)
        door_x = v1x + v1w / 2 - 0.7
    else:               # modern gable: graphite barn with full-height gable glazing and timber frame + flat wing
        bw, bx = W * 0.6, -W * 0.18
        bd = D + 0.3
        gable_body(f"{tag}_barn", bw, bd, 3.1, 2.1, (bx, gy, Z0), M("graphite"), c, root)
        gable_roof(tag, c, root, bx, gy, bw, bd, 3.1 + Z0, 2.1, material="roof_metal", extra=0.9)
        for sx in (-1, 1):   # timber frame around the gable end
            box(f"{tag}_frame{sx}", (0.22, 0.5, 3.1), (bx + sx * (bw / 2 - 0.05), gy - bd / 2 - 0.2, Z0), M("clad_wood"), c, parent=root)
        panoramic(root, f"{tag}_gpano", c, bx, gy - bd / 2, Z0 + 0.1, bw * 0.7, 2.9, 3)
        box(f"{tag}_gtri", (bw * 0.46, 0.06, 1.4), (bx, gy - bd / 2 - 0.03, Z0 + 3.05), _pane_mat(), c, parent=root)
        _win_group(root, bw, bd, gy, Z0 + 0.5, 1.9, c, f"{tag}_g", xoff=bx, front=False)
        ww = W * 0.4
        wx = bx + bw / 2 + ww / 2
        box(f"{tag}_wing", (ww, D - 0.6, 2.9), (wx, gy + 0.3, Z0), main, c, parent=root)
        panoramic(root, f"{tag}_wpano", c, wx, gy + 0.3 - (D - 0.6) / 2, Z0 + 0.15, ww * 0.75, 2.4, 2)
        roof_slab(root, f"{tag}_wroof", c, wx, gy + 0.3, Z0 + 2.9, ww + 0.4, D - 0.2, led_front=gy + 0.3 - (D - 0.2) / 2)
        door_x = bx - bw * 0.3
        garage = False

    # entrance: door, slim canopy, house-number light
    box(f"{tag}_door", (1.0, 0.12, 2.3), (door_x, yf - 0.04, Z0), M("wood"), c, parent=root)
    box(f"{tag}_canopy", (1.8, 1.1, 0.1), (door_x, yf - 0.55, Z0 + 2.55), M("graphite"), c, parent=root)
    box(f"{tag}_canopyLED", (1.5, 0.05, 0.03), (door_x, yf - 0.9, Z0 + 2.52), M("led_warm"), c, parent=root)
    box(f"{tag}_number", (0.35, 0.05, 0.12), (door_x + 0.85, yf - 0.06, Z0 + 1.9), M("led_warm"), c, parent=root)

    if garage:
        gx = W / 2 + 1.4
        box(f"{tag}_garage", (3.0, 4.4, 2.7), (gx, gy + 0.1, 0), M("graphite"), c, parent=root)
        box(f"{tag}_garage_door", (2.5, 0.08, 2.15), (gx, gy + 0.1 - 2.22, 0), M("clad_wood"), c, parent=root)
        box(f"{tag}_garage_roof", (3.3, 4.8, 0.16), (gx, gy - 0.1, 2.7), M("graphite"), c, parent=root)
        box(f"{tag}_garage_light", (2.4, 0.06, 0.04), (gx, gy + 0.1 - 2.45, 2.66), M("led_warm"), c, parent=root)
    else:               # carport: slim timber roof on steel posts
        box(f"{tag}_carport", (3.3, 4.8, 0.16), (W / 2 + 1.4, gy - 0.2, 2.6), M("clad_wood"), c, parent=root)
        box(f"{tag}_carportLED", (3.0, 0.06, 0.04), (W / 2 + 1.4, gy - 2.45, 2.56), M("led_warm"), c, parent=root)
        for py in (-2.1, 2.1):
            box(f"{tag}_cp_post{py}", (0.1, 0.1, 2.6), (W / 2 + 2.9, gy - 0.2 + py, 0), M("steel"), c, parent=root)

    # one green garden tree per lot
    ty = (x - 4.3 if face_south else x + 4.3, y + (3.0 if face_south else -3.0), WALK_H)
    tree(f"{tag}_tree", ty, size=0.85, shape="round" if idx % 2 else "columnar")


def free_plot(idx, x, y):
    c = coll("FreePlots")
    tag = f"FreePlot_{idx:02d}"
    root = bpy.data.objects.new(tag, None)
    c.objects.link(root)
    root.location = (x, y, WALK_H)
    box(f"{tag}_lawn", (10.2, 8.4, 0.05), (0, 0, -0.04), M("lawn_fine"), c, parent=root)
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
            tree(f"T_corner_{sx}_{sy}", (sx * 7.6, sy * 7.4, WALK_H), shape="columnar", size=0.8)
    # shrubs and flower beds along the front street (foreground)
    for k, x in enumerate(range(-30, 31, 4)):
        if abs(x) < 8:
            continue
        shrub(f"S_front_{k}", (x + random.uniform(-0.6, 0.6), -23.8, WALK_H), random.uniform(0.4, 0.6))
    for k, x in enumerate((-15, -25, 15, 25)):
        flowerbed(f"Bed_front_{k}", (x, -36.6, 0), 3.2, 1.0, coll("Trees"))
    # flowering trees along the avenue approach
    for k, y in enumerate(range(-58, -38, 7)):
        tree(f"T_ave_L{k}", (-7.6, y, 0), shape="columnar", size=1.0)
        tree(f"T_ave_R{k}", (7.6, y, 0), shape="columnar", size=1.0)
    # foreground clusters & meadows
    for k in range(140):
        x = random.uniform(-110, 110)
        y = random.uniform(-110, -38)
        if abs(x) < 7 or abs(y + 30) < 7:
            continue
        tree(f"T_meadow_{k}", (x, y, 0), size=random.uniform(0.9, 1.5))
    for k in range(60):
        x = random.choice([random.uniform(-110, -42), random.uniform(42, 110)])
        y = random.uniform(-36, 33)
        tree(f"T_edge_{k}", (x, y, 0), size=random.uniform(0.9, 1.4))
    # hero foreground framing trees (bottom corners of the vertical frame)
    tree("T_hero_L", (-17.5, -44, 0), shape="layered", size=1.3)
    tree("T_hero_R", (13, -42, 0), shape="round", size=1.1)


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
        kind = random.choices(["box", "setback", "round", "slant", "twin"], weights=[3, 3, 2, 2, 1])[0]
        if kind == "setback":          # stepped tiers
            box(f"Tower_{k}", (w, d, h * 0.6), (x, y, -0.9), M("tower_lit"), c)
            box(f"Tower_{k}_t2", (w * 0.75, d * 0.75, h * 0.28), (x, y, h * 0.6 - 0.9), M("tower_lit"), c)
            box(f"Tower_{k}_t3", (w * 0.5, d * 0.5, h * 0.17), (x, y, h * 0.88 - 0.9), M("tower_lit"), c)
        elif kind == "round":          # cylindrical tower with a crown ring
            cyl(f"Tower_{k}", w / 2, w / 2 * 0.92, h, 14, (x, y, -0.9), M("tower_lit"), c)
            cyl(f"Tower_{k}_ring", w / 2 * 0.95, w / 2 * 0.95, 0.8, 14, (x, y, h - 1.6), M("lamp"), c)
        elif kind == "slant":          # sloped crown
            box(f"Tower_{k}", (w, d, h * 0.88), (x, y, -0.9), M("tower_lit"), c)
            t = box(f"Tower_{k}_slant", (w * 1.02, d * 1.02, h * 0.2), (x, y, h * 0.8 - 0.9), M("tower_lit"), c)
            t.rotation_euler.x = math.radians(18)
        elif kind == "twin":           # two slender towers with a sky bridge
            for sx in (-1, 1):
                box(f"Tower_{k}_{sx}", (w * 0.4, d * 0.6, h * (1.0 if sx < 0 else 0.86)), (x + sx * w * 0.32, y, -0.9), M("tower_lit"), c)
            box(f"Tower_{k}_bridge", (w * 0.5, d * 0.4, 1.4), (x, y, h * 0.6 - 0.9), M("lamp"), c)
        else:
            box(f"Tower_{k}", (w, d, h), (x, y, -0.9), M("tower_lit"), c)
        if random.random() < 0.3:
            cyl(f"Tower_{k}_spire", 0.25, 0.05, h * 0.18, 6, (x, y, h - 0.9), M("graphite"), c)
            box(f"Tower_{k}_beacon", (0.5, 0.5, 0.8), (x, y, h * 1.17 - 0.9), M("lamp"), c)
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
