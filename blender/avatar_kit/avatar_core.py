"""NO ONE'S CITY — Avatar Kit (M0.7): generic stylized resident generator.

Builds a rigged, game-ready stylized human from a *resident config* (JSON / dict):
  * body, head & face, hair, eyes, brows, nose, mouth, ears, glasses, clothes, shoes, accessories
  * armature (Root, Pelvis, Spine, Chest, Neck, Head, Shoulder/UpperArm/Forearm/Hand .L/.R,
    Thigh/Shin/Foot .L/.R) with distance-based smooth skin weights
  * a small pose library (neutral A-pose = rest, relaxed, test poses)
  * validation helpers (parts, penetration, deformation, scale)

Everything is procedural: no external textures, fonts or add-ons. Blender 4.2+.
Style: Modern Stylized 3D x Premium Low-Poly x Cozy Cinematic.

The base logic knows nothing about a particular resident. Swap styles / colours / proportions in the
config: hair.style, glasses.style, accessories, outfit colours, face proportions, height, placement.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# --------------------------------------------------------------------------- defaults

DEFAULT_CONFIG = {
    "id": "resident",
    "display_name": "Resident",
    "height": 1.78,                      # stylized model height (m); not a claim about the real person
    "build": {"shoulder_width": 0.40, "chest": 1.0, "waist": 1.0, "hips": 1.0, "arm_thickness": 1.0, "leg_thickness": 1.0},
    "skin": {"tone": "#c68a5e", "lip": "#a8644a", "blush": "#c27a56"},
    "face": {
        "head_width": 1.0, "head_height": 1.0, "head_depth": 1.0,
        "jaw_width": 1.0, "chin_forward": 0.0, "cheek_fullness": 1.0,
        "brow_thickness": 1.0, "brow_angle_deg": 6.0, "nose_size": 1.0, "smile": 1.0,
        "eye_color": "#3a2618",
    },
    "hair": {"style": "short_textured_fade", "color": "#141210", "fade_color": "#2b2420", "top_height": 1.0, "spikiness": 1.0},
    "brows": {"color": "#16110e"},
    "glasses": {"style": "rect_fullrim", "frame_color": "#d4a64a", "lens_color": "#8a5a22", "lens_tint": 0.65},
    "outfit": {
        "shirt": {"style": "open_collar_rolled", "color": "#f2f0ec", "button_color": "#e6e2da"},
        "trousers": {"style": "slim", "color": "#26282d"},
        "shoes": {"style": "sneaker", "color": "#f4f3f0", "sole_color": "#e2e0db"},
    },
    "accessories": [{"type": "watch", "side": "L", "case_color": "#b9bcc0", "dial_color": "#1d1f24"}],
    "placement": {"location": [0.0, 0.0, 0.0], "rotation_z_deg": 0.0, "pose": "relaxed"},
}


def merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# --------------------------------------------------------------------------- materials

def make_materials(cfg, prefix):
    def m(name, color, rough=0.6, metallic=0.0, spec=0.5, sss=0.0, trans=0.0, emit=None, es=0.0, coat=0.0):
        full = f"{prefix}_{name}"
        old = bpy.data.materials.get(full)
        if old:
            bpy.data.materials.remove(old)
        mt = bpy.data.materials.new(full)
        mt.use_nodes = True
        b = mt.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*srgb(color), 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metallic
        b.inputs["Specular IOR Level"].default_value = spec
        if sss:
            b.inputs["Subsurface Weight"].default_value = sss
            b.inputs["Subsurface Radius"].default_value = (0.9, 0.45, 0.3)
            b.inputs["Subsurface Scale"].default_value = 0.01
        if trans:
            b.inputs["Transmission Weight"].default_value = trans
            b.inputs["IOR"].default_value = 1.45
        if coat:
            b.inputs["Coat Weight"].default_value = coat
        if emit:
            b.inputs["Emission Color"].default_value = (*srgb(emit), 1)
            b.inputs["Emission Strength"].default_value = es
        return mt

    o = cfg["outfit"]
    g = cfg["glasses"]
    mats = {
        "skin": m("skin", cfg["skin"]["tone"], 0.55),
        "lip": m("lip", cfg["skin"]["lip"], 0.5, sss=0.1),
        "hair": m("hair", cfg["hair"]["color"], 0.85, spec=0.25),
        "fade": m("hair_fade", cfg["hair"]["fade_color"], 0.85),
        "brow": m("brows", cfg["brows"]["color"], 0.8),
        "sclera": m("eye_white", "#f2eee8", 0.3),
        "iris": m("eye_iris", cfg["face"]["eye_color"], 0.2, coat=1.0),
        "teeth": m("teeth", "#f4f1ea", 0.35),
        "mouth": m("mouth_line", "#5a2c22", 0.7),
        "frame": m("glasses_frame", g["frame_color"], 0.25, metallic=1.0),
        "lens": m("glasses_lens", g["lens_color"], 0.05, spec=0.9, trans=1.0 - g["lens_tint"] * 0.6),
        "shirt": m("shirt", o["shirt"]["color"], 0.75, sss=0.05),
        "button": m("buttons", o["shirt"]["button_color"], 0.35),
        "trousers": m("trousers", o["trousers"]["color"], 0.8),
        "shoe": m("shoes", o["shoes"]["color"], 0.45),
        "sole": m("soles", o["shoes"]["sole_color"], 0.6),
        "lace": m("laces", "#ffffff", 0.6),
        "steel": m("watch_steel", "#b9bcc0", 0.25, metallic=1.0),
        "dial": m("watch_dial", "#1d1f24", 0.2, coat=1.0),
        "index": m("watch_index", "#e8e6e0", 0.3, metallic=0.5),
    }
    for a in cfg["accessories"]:
        if a["type"] == "watch":
            mats["steel"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*srgb(a["case_color"]), 1)
            mats["dial"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*srgb(a["dial_color"]), 1)
    return mats


# --------------------------------------------------------------------------- mesh helpers

class Builder:
    def __init__(self, cfg, collection, mats, prefix):
        self.cfg, self.col, self.mats, self.prefix = cfg, collection, mats, prefix
        self.parts = {}       # role -> object
        self.bind = {}        # object name -> list of allowed bones (or single rigid bone)

    def obj(self, role, bm, mat, bones, smooth=True, subdiv=0):
        name = f"{self.prefix}_{role}"
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(self.mats[mat])
        ob = bpy.data.objects.new(name, me)
        self.col.objects.link(ob)
        if subdiv:
            mod = ob.modifiers.new("sub", "SUBSURF")
            mod.levels = mod.render_levels = subdiv
            dg = bpy.context.evaluated_depsgraph_get()
            new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            old = ob.data
            ob.data = new
            new.name = name
            bpy.data.meshes.remove(old)
        for p in ob.data.polygons:
            p.use_smooth = smooth
        self.parts[role] = ob
        self.bind[ob.name] = bones
        return ob

    # superellipse ring
    @staticmethod
    def ring(bm, c, u, v, rx, ry, segs, power=2.0):
        vs = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            x = math.copysign(abs(ca) ** (2 / power), ca)
            y = math.copysign(abs(sa) ** (2 / power), sa)
            vs.append(bm.verts.new(c + u * (rx * x) + v * (ry * y)))
        return vs

    def loft(self, role, rings, mat, bones, segs=16, cap0=False, cap1=False, subdiv=1):
        """rings: list of (centre, u, v, rx, ry, power). Builds a smooth tube."""
        bm = bmesh.new()
        rs = [self.ring(bm, Vector(c), Vector(u), Vector(v), rx, ry, segs, p) for c, u, v, rx, ry, p in rings]
        for a, b in zip(rs, rs[1:]):
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((a[i], a[j], b[j], b[i]))
        if cap0:
            bm.faces.new(rs[0][::-1])
        if cap1:
            bm.faces.new(rs[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.obj(role, bm, mat, bones, subdiv=subdiv)

    def ellipsoid(self, role, c, r, mat, bones, segs=(16, 10), rot=None, subdiv=0):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segs[0], v_segments=segs[1], radius=1.0)
        S = Matrix.Diagonal((*r, 1.0))
        R = rot.to_4x4() if rot is not None else Matrix.Identity(4)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ R @ S, verts=bm.verts)
        return self.obj(role, bm, mat, bones, subdiv=subdiv)

    def rbox(self, role, c, size, mat, bones, rot=None, subdiv=2, smooth=True):
        """Rounded box (subdivided cube) — sneakers, palms, buttons."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        S = Matrix.Diagonal((*size, 1.0))
        R = rot.to_4x4() if rot is not None else Matrix.Identity(4)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ R @ S, verts=bm.verts)
        return self.obj(role, bm, mat, bones, smooth=smooth, subdiv=subdiv)

    def box(self, role, c, size, mat, bones, rot=None):
        return self.rbox(role, c, size, mat, bones, rot, subdiv=0, smooth=False)


def frame_along(d):
    """Orthonormal (u, v) perpendicular to direction d, with v ~ world Y."""
    d = d.normalized()
    v = Vector((0, 1, 0))
    v = (v - d * v.dot(d)).normalized()
    u = v.cross(d).normalized()
    return u, v


# --------------------------------------------------------------------------- skeleton

REST_ARM_DEG = 32.0      # neutral rest A-pose: arms 32 deg from vertical


def skeleton_points(cfg):
    """Rest (A-pose) joint positions in metres, character facing -Y, feet on z = 0."""
    s = cfg["height"] / 1.78
    b = cfg["build"]
    sh = b["shoulder_width"] / 2
    P = {}
    P["pelvis"] = Vector((0, 0, 0.95)) * s
    P["spine"] = Vector((0, 0, 1.06)) * s
    P["chest"] = Vector((0, 0, 1.25)) * s
    P["neck"] = Vector((0, 0.005, 1.45)) * s
    P["head"] = Vector((0, 0.0, 1.565)) * s
    P["head_top"] = Vector((0, 0.0, 1.78)) * s
    arm_dir = Vector((math.sin(math.radians(REST_ARM_DEG)), 0, -math.cos(math.radians(REST_ARM_DEG))))
    for side, sx in (("L", 1), ("R", -1)):
        P[f"clav_{side}"] = Vector((0.025 * sx, 0.0, 1.415)) * s
        P[f"shoulder_{side}"] = Vector((sh * sx, 0.0, 1.43)) * s
        d = Vector((arm_dir.x * sx, 0, arm_dir.z))
        P[f"elbow_{side}"] = P[f"shoulder_{side}"] + d * 0.29 * s
        P[f"wrist_{side}"] = P[f"elbow_{side}"] + d * 0.26 * s
        P[f"hand_{side}"] = P[f"wrist_{side}"] + d * 0.17 * s
        P[f"hip_{side}"] = Vector((0.09 * sx, 0.0, 0.93)) * s
        P[f"knee_{side}"] = Vector((0.092 * sx, -0.01, 0.51)) * s
        P[f"ankle_{side}"] = Vector((0.094 * sx, 0.015, 0.085)) * s
        P[f"toe_{side}"] = Vector((0.097 * sx, -0.135, 0.025)) * s
    return P, s


BONES = [  # name, head key, tail key, parent
    ("Root", None, None, None),
    ("Pelvis", "pelvis", "spine", "Root"),
    ("Spine", "spine", "chest", "Pelvis"),
    ("Chest", "chest", "neck", "Spine"),
    ("Neck", "neck", "head", "Chest"),
    ("Head", "head", "head_top", "Neck"),
]
for _s in ("L", "R"):
    BONES += [
        (f"Shoulder.{_s}", f"clav_{_s}", f"shoulder_{_s}", "Chest"),
        (f"UpperArm.{_s}", f"shoulder_{_s}", f"elbow_{_s}", f"Shoulder.{_s}"),
        (f"Forearm.{_s}", f"elbow_{_s}", f"wrist_{_s}", f"UpperArm.{_s}"),
        (f"Hand.{_s}", f"wrist_{_s}", f"hand_{_s}", f"Forearm.{_s}"),
        (f"Thigh.{_s}", f"hip_{_s}", f"knee_{_s}", "Pelvis"),
        (f"Shin.{_s}", f"knee_{_s}", f"ankle_{_s}", f"Thigh.{_s}"),
        (f"Foot.{_s}", f"ankle_{_s}", f"toe_{_s}", f"Shin.{_s}"),
    ]


def build_armature(name, col, P, s):
    data = bpy.data.armatures.new(name)
    data.display_type = "OCTAHEDRAL"
    arm = bpy.data.objects.new(name, data)
    col.objects.link(arm)
    arm.show_in_front = True
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for n, h, t, parent in BONES:
        b = data.edit_bones.new(n)
        if n == "Root":
            b.head, b.tail = Vector((0, 0, 0)), Vector((0, 0.25 * s, 0))
        else:
            b.head, b.tail = P[h], P[t]
        if parent:
            b.parent = eb[parent]
        b.use_deform = n != "Root"
        eb[n] = b
    for side in ("L", "R"):          # keep arm/leg rolls predictable for posing
        for bn in (f"UpperArm.{side}", f"Forearm.{side}", f"Hand.{side}"):
            eb[bn].align_roll(Vector((0, -1, 0)))
        for bn in (f"Thigh.{side}", f"Shin.{side}"):
            eb[bn].align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def bone_segments(arm):
    return {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in arm.data.bones if b.use_deform}


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def skin(builder, arm):
    """Distance-based smooth weights restricted to each part's allowed bones (max 2 influences)."""
    segs = bone_segments(arm)
    for ob in builder.parts.values():
        bones = builder.bind[ob.name]
        ob.parent = arm
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        if isinstance(bones, str):
            vg = ob.vertex_groups.new(name=bones)
            vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
            continue
        groups = {bn: ob.vertex_groups.new(name=bn) for bn in bones}
        for v in ob.data.vertices:
            ws = sorted(((1.0 / (seg_dist(v.co, *segs[bn]) + 0.012) ** 4, bn) for bn in bones), reverse=True)[:2]
            tot = sum(w for w, _ in ws)
            for w, bn in ws:
                w /= tot
                if w > 0.04:
                    groups[bn].add([v.index], w, "REPLACE")


# --------------------------------------------------------------------------- body & clothes

def build_body(B, P, s):
    cfg = B.cfg
    bw = cfg["build"]
    Z = lambda z: z * s  # noqa: E731
    X, Y, U = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

    # ---- shirt torso (untucked, slightly boxy athletic fit)
    ch, wa, hp = bw["chest"], bw["waist"], bw["hips"]
    torso = [
        (0.875, 0.188 * hp, 0.127, 2.4), (0.95, 0.182 * hp, 0.122, 2.4), (1.05, 0.168 * wa, 0.117, 2.4),
        (1.16, 0.172 * wa, 0.12, 2.4), (1.27, 0.192 * ch, 0.128, 2.4), (1.36, 0.2 * ch, 0.128, 2.3),
        (1.415, 0.19 * ch, 0.115, 2.1), (1.445, 0.17 * ch, 0.104, 2.0), (1.475, 0.125, 0.085, 2.0), (1.5, 0.078, 0.07, 2.0),
    ]
    B.loft("shirt_torso", [((0, 0.0, Z(z)), X, Y, rx * s, ry * s, p) for z, rx, ry, p in torso], "shirt",
           ["Pelvis", "Spine", "Chest", "Neck", "Shoulder.L", "Shoulder.R"], segs=20, cap0=False)
    # hem band + placket + buttons + open collar
    B.loft("shirt_hem", [((0, 0, Z(0.872)), X, Y, 0.191 * hp * s, 0.13 * s, 2.4), ((0, 0, Z(0.892)), X, Y, 0.191 * hp * s, 0.13 * s, 2.4)],
           "shirt", ["Pelvis", "Spine"], segs=20, subdiv=1)
    front_y = lambda z: -0.123 * s if z > 1.2 else -0.12 * s  # noqa: E731
    B.box("shirt_placket", Vector((0, -0.124 * s, Z(1.12))), (0.03 * s, 0.006, 0.47 * s), "shirt", ["Spine", "Chest"])
    for i, z in enumerate((0.92, 1.03, 1.14, 1.25, 1.33)):
        B.ellipsoid(f"shirt_button{i}", Vector((0, -0.13 * s, Z(z))), (0.006, 0.003, 0.006), "button", "Chest" if z > 1.2 else "Spine", segs=(10, 6))
    # open collar: two collar points lying on the upper chest, a standing band, skin visible in the V
    for sx, side in ((1, "L"), (-1, "R")):
        pts = [(0.022, -0.072, 1.515), (0.088, -0.08, 1.478), (0.072, -0.128, 1.398), (0.014, -0.126, 1.43)]
        bm = bmesh.new()
        vs = [bm.verts.new(Vector((x * sx * s, y * s, z * s))) for x, y, z in pts]
        f = bm.faces.new(vs if sx > 0 else vs[::-1])
        bmesh.ops.recalc_face_normals(bm, faces=[f])
        if f.normal.y > 0:
            f.normal_flip()
        bmesh.ops.solidify(bm, geom=bm.faces, thickness=0.004)
        B.obj(f"collar_{side}", bm, "shirt", ["Neck", "Chest"], smooth=False)
    B.loft("collar_band", [((0, 0.008, Z(1.475)), X, Y, 0.072 * s, 0.066 * s, 2.0), ((0, 0.014, Z(1.536)), X, Y, 0.07 * s, 0.064 * s, 2.0)],
           "shirt", ["Neck", "Chest"], segs=16, subdiv=1)
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p) * s) for p in ((-0.024, -0.104, 1.47), (0.024, -0.104, 1.47), (0.0, -0.124, 1.385))]
    bm.faces.new(vs)
    bmesh.ops.solidify(bm, geom=bm.faces, thickness=0.003)
    B.obj("chest_v", bm, "skin", ["Chest", "Neck"], smooth=True)

    # ---- neck
    B.loft("neck", [((0, 0.008, Z(1.43)), X, Y, 0.064 * s, 0.062 * s, 2.0), ((0, 0.006, Z(1.53)), X, Y, 0.062 * s, 0.06 * s, 2.0),
                    ((0, 0.0, Z(1.6)), X, Y, 0.056 * s, 0.055 * s, 2.0)], "skin", ["Chest", "Neck", "Head"], segs=14)

    # ---- arms: rolled sleeves, cuff roll, forearm skin, hands
    at = bw["arm_thickness"]
    for side, sx in (("L", 1), ("R", -1)):
        sh, el, wr, hd = P[f"shoulder_{side}"], P[f"elbow_{side}"], P[f"wrist_{side}"], P[f"hand_{side}"]
        d1, d2 = (el - sh).normalized(), (wr - el).normalized()
        u1, v1 = frame_along(d1)
        u2, v2 = frame_along(d2)
        sleeve = [(sh - Vector((0.045 * sx, 0, 0.012)) * s, 0.066), (sh + d1 * 0.03 * s, 0.069), (sh + d1 * 0.1 * s, 0.066), (sh + d1 * 0.2 * s, 0.06),
                  (el, 0.055), (el + d2 * 0.06 * s, 0.052)]
        B.loft(f"sleeve_{side}", [(c, u1 if i < 5 else u2, v1 if i < 5 else v2, r * at * s, r * at * s * 0.95, 2.0) for i, (c, r) in enumerate(sleeve)],
               "shirt", [f"Shoulder.{side}", f"UpperArm.{side}", f"Forearm.{side}", "Chest"], segs=14)
        cuff = [(el + d2 * 0.035 * s, 0.058), (el + d2 * 0.065 * s, 0.062), (el + d2 * 0.1 * s, 0.059)]
        B.loft(f"cuff_{side}", [(c, u2, v2, r * at * s, r * at * s, 2.0) for c, r in cuff], "shirt", [f"Forearm.{side}"], segs=14)
        fore = [(el + d2 * 0.03 * s, 0.047), (el + d2 * 0.12 * s, 0.045), (el + d2 * 0.2 * s, 0.038), (wr, 0.031), (wr + d2 * 0.02 * s, 0.03)]
        B.loft(f"forearm_{side}", [(c, u2, v2, r * at * s, r * at * s * 0.85, 2.0) for c, r in fore], "skin",
               [f"Forearm.{side}", f"Hand.{side}"], segs=12, cap1=True)
        # hand: palm + four fingers + thumb (palm faces down-inward, thumb forward)
        dh = (hd - wr).normalized()
        uh, vh = frame_along(dh)               # uh: palm normal side, vh: across the knuckles (~Y)
        rot = Matrix((uh, vh, dh)).transposed()
        palm_c = wr + dh * 0.055 * s
        B.rbox(f"palm_{side}", palm_c, (0.03 * s, 0.085 * s, 0.1 * s), "skin", [f"Hand.{side}", f"Forearm.{side}"], rot=rot, subdiv=2)
        for k, off in enumerate((-0.03, -0.01, 0.01, 0.029)):
            ln = (0.07, 0.078, 0.074, 0.06)[k] * s
            c0 = wr + dh * 0.105 * s + vh * off * s
            dfing = (dh * math.cos(math.radians(14)) - uh * math.sin(math.radians(14))).normalized()   # gentle curl
            uf, vf = frame_along(dfing)
            B.loft(f"finger{k}_{side}", [(c0, uf, vf, 0.0095 * s, 0.0105 * s, 2.0), (c0 + dfing * ln * 0.55, uf, vf, 0.009 * s, 0.0098 * s, 2.0),
                                          (c0 + dfing * ln, uf, vf, 0.0078 * s, 0.0085 * s, 2.0)], "skin", f"Hand.{side}", segs=8, cap1=True)
        dth = (dh * 0.55 - vh * 0.75 - uh * 0.35).normalized()
        uth, vth = frame_along(dth)
        c0 = wr + dh * 0.03 * s - vh * 0.035 * s
        B.loft(f"thumb_{side}", [(c0, uth, vth, 0.013 * s, 0.012 * s, 2.0), (c0 + dth * 0.045 * s, uth, vth, 0.011 * s, 0.01 * s, 2.0),
                                 (c0 + dth * 0.07 * s, uth, vth, 0.0085 * s, 0.0085 * s, 2.0)], "skin", f"Hand.{side}", segs=8, cap1=True)

    # ---- trousers: seat block + slim tapered legs, shoes
    lt = bw["leg_thickness"]
    B.loft("trousers_seat", [((0, 0.003, Z(z)), X, Y, rx * hp * s, ry * s, 2.4) for z, rx, ry in
                             ((0.99, 0.158, 0.104), (0.93, 0.165, 0.109), (0.86, 0.166, 0.11), (0.8, 0.148, 0.099))],
           "trousers", ["Pelvis", "Thigh.L", "Thigh.R"], segs=20, cap1=True)
    for side, sx in (("L", 1), ("R", -1)):
        hip, kn, an = P[f"hip_{side}"], P[f"knee_{side}"], P[f"ankle_{side}"]
        leg = [(hip.lerp(kn, 0.1), 0.086), (hip.lerp(kn, 0.3), 0.082), (hip.lerp(kn, 0.7), 0.07), (kn, 0.062),
               (kn.lerp(an, 0.45), 0.056), (kn.lerp(an, 0.85), 0.051), (an + Vector((0, 0, 0.01 * s)), 0.051)]
        B.loft(f"leg_{side}", [(c, X, Y, r * lt * s, r * lt * s * 0.97, 2.0) for c, r in leg], "trousers",
               ["Pelvis", f"Thigh.{side}", f"Shin.{side}"], segs=16)
        # sneaker: rounded upper, thick sole, laces, heel tab
        foot_c = Vector((P[f"ankle_{side}"].x, -0.045 * s, 0.05 * s))
        B.rbox(f"shoe_{side}", foot_c, (0.1 * s, 0.27 * s, 0.085 * s), "shoe", f"Foot.{side}", subdiv=2)
        B.rbox(f"sole_{side}", foot_c + Vector((0, 0, -0.035 * s)), (0.108 * s, 0.285 * s, 0.03 * s), "sole", f"Foot.{side}", subdiv=1)
        for k in range(3):
            B.box(f"lace{k}_{side}", foot_c + Vector((0, -0.03 * s - k * 0.025 * s, 0.043 * s)), (0.04 * s, 0.008, 0.006), "lace", f"Foot.{side}",
                  rot=Matrix.Rotation(math.radians(-25), 3, "X"))
        B.rbox(f"tongue_{side}", foot_c + Vector((0, 0.005 * s, 0.05 * s)), (0.05 * s, 0.05 * s, 0.03 * s), "shoe", f"Foot.{side}", subdiv=1)


# --------------------------------------------------------------------------- head & face

def build_head(B, P, s):
    cfg = B.cfg
    f = cfg["face"]
    rx, ry, rz = 0.084 * f["head_width"] * s, 0.098 * f["head_depth"] * s, 0.116 * f["head_height"] * s
    C = Vector((0, -0.004 * s, 1.664 * s))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=20, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        X, Y, Z = x * rx, y * ry, z * rz
        if z < -0.15:                                   # broad, full jaw and lower face
            k = min(1.0, (-z - 0.15) / 0.55)
            X *= 1.0 + 0.09 * k * f["jaw_width"] - 0.2 * max(0.0, (-z - 0.75) / 0.25)
            Z *= 1.0 + 0.05 * k * f.get("jaw_drop", 0.0)
        if y < 0:                                       # flatter face plane
            Y *= 0.9
        if y < -0.3 and -0.55 < z < 0.15 and abs(x) > 0.35:
            X *= 1.0 + 0.05 * f["cheek_fullness"]       # full cheeks
            Y *= 1.0 + 0.04 * f["cheek_fullness"]
        if z < -0.65 and y < -0.2:
            Y -= (0.006 + 0.01 * f["chin_forward"]) * s     # chin
        if y > 0.2 and z > -0.2:
            Y *= 1.05                                   # rounded back of the skull
        v.co = C + Vector((X, Y, Z))
    B.obj("head", bm, "skin", "Head", subdiv=1)
    head = B.parts["head"]

    # surface probe for placing features on the face
    bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())

    def surf(x, z, inset=0.0):
        o = Vector((x, -0.5, z))
        hit, n, _i, _d = bvh.ray_cast(o, Vector((0, 1, 0)))
        return Vector((x, (hit.y if hit else -0.09 * s) + inset, z))

    ez = 1.682 * s
    ex = 0.031 * s
    # ears
    for sx, side in ((1, "L"), (-1, "R")):
        rot = Matrix.Rotation(math.radians(-12 * sx), 3, "Z")
        B.ellipsoid(f"ear_{side}", Vector((0.083 * sx * f["head_width"] * s, 0.006 * s, 1.662 * s)), (0.013 * s, 0.03 * s, 0.036 * s), "skin", "Head",
                    segs=(12, 8), rot=rot, subdiv=1)
    # eyes (set into the face, mostly seen through the tinted lenses)
    for sx, side in ((1, "L"), (-1, "R")):
        p = surf(ex * sx, ez)
        B.ellipsoid(f"eye_{side}", p + Vector((0, 0.008 * s, 0)), (0.0135 * s, 0.009 * s, 0.0085 * s), "sclera", "Head", segs=(14, 10))
        B.ellipsoid(f"iris_{side}", p + Vector((0, 0.0005, 0)), (0.0062 * s, 0.002, 0.0062 * s), "iris", "Head", segs=(12, 8))
    # thick dark brows
    bt = f["brow_thickness"]
    for sx, side in ((1, "L"), (-1, "R")):
        p = surf(0.032 * s * sx, 1.708 * s, -0.003)
        rot = Matrix.Rotation(math.radians(f["brow_angle_deg"] * sx), 3, "Y") @ Matrix.Rotation(math.radians(-8 * sx), 3, "Z")
        B.rbox(f"brow_{side}", p, (0.044 * s, 0.009, 0.012 * s * bt), "brow", "Head", rot=rot, subdiv=1)
    # nose: bridge + rounded tip with nostril wings
    ns = f["nose_size"]
    tip = surf(0.0, 1.643 * s, -0.012 * ns)
    B.ellipsoid("nose_tip", tip, (0.014 * s * ns, 0.012 * s * ns, 0.013 * s * ns), "skin", "Head", segs=(12, 8), subdiv=1)
    br = surf(0.0, 1.672 * s, -0.004)
    B.rbox("nose_bridge", (br + tip) / 2 + Vector((0, 0.004, 0)), (0.013 * s, 0.016 * s, 0.045 * s * ns), "skin", "Head",
           rot=Matrix.Rotation(math.radians(-14), 3, "X"), subdiv=1)
    for sx, side in ((1, "L"), (-1, "R")):
        B.ellipsoid(f"nostril_{side}", tip + Vector((0.011 * s * sx, 0.006, -0.004 * s)), (0.0075 * s, 0.007 * s, 0.006 * s), "skin", "Head", segs=(10, 6))
    # smile: curved mouth line, upper teeth, lower lip
    sm = f["smile"]
    bm = bmesh.new()
    pts = []
    for i in range(11):
        x = (-0.027 + 0.054 * i / 10) * s
        z = 1.608 * s + 7.5 * sm * (x / s) ** 2 * s
        pts.append(surf(x, z, -0.0015))
    top = [bm.verts.new(p + Vector((0, 0, 0.0018))) for p in pts]
    bot = [bm.verts.new(p - Vector((0, 0, 0.0018))) for p in pts]
    for i in range(10):
        bm.faces.new((top[i], top[i + 1], bot[i + 1], bot[i]))
    B.obj("mouth_line", bm, "mouth", "Head", smooth=False)
    bm = bmesh.new()
    t_top = [bm.verts.new(p + Vector((0, 0.0005, 0.0015))) for p in pts[2:9]]
    t_bot = [bm.verts.new(p + Vector((0, 0.0005, -0.0045))) for p in pts[2:9]]
    for i in range(6):
        bm.faces.new((t_top[i], t_top[i + 1], t_bot[i + 1], t_bot[i]))
    B.obj("teeth", bm, "teeth", "Head", smooth=False)
    lip = surf(0.0, 1.598 * s, -0.004)
    B.ellipsoid("lower_lip", lip, (0.021 * s, 0.006 * s, 0.005 * s), "lip", "Head", segs=(12, 6))
    return head, bvh, surf


def build_hair(B, head, cfg, s):
    """Short textured top + skin fade on the sides, built as offset shells of the skull."""
    h = cfg["hair"]
    me = head.data
    C = Vector((0, -0.004 * s, 1.664 * s))
    import random
    rnd = random.Random(7)

    def shell(role, keep, thick, mat, spikes=0.0, smooth=True):
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.normal_update()
        drop = [v for v in bm.verts if not keep(v.co)]
        bmesh.ops.delete(bm, geom=drop, context="VERTS")
        for v in bm.verts:
            t = thick(v.co)
            if spikes:
                t += rnd.uniform(0, spikes) * max(0.0, (v.co.z - 1.70 * s) / (0.08 * s))
            v.co += (v.co - C).normalized() * t
        bmesh.ops.solidify(bm, geom=bm.faces, thickness=-0.002)
        B.obj(role, bm, mat, "Head", subdiv=0, smooth=smooth)

    style = h["style"]
    if style == "short_textured_fade":
        hairline_front = 1.736 * s
        top_h = 0.02 * h["top_height"] * s

        def keep_top(c):
            front = c.y < -0.04 * s
            return c.z > (hairline_front if front else 1.705 * s) and not (abs(c.x) > 0.07 * s and c.z < 1.735 * s and c.y > -0.05 * s)

        def thick_top(c):
            k = max(0.0, min(1.0, (c.z - 1.70 * s) / (0.06 * s)))
            return 0.004 + top_h * k

        shell("hair_top", keep_top, thick_top, "hair", spikes=0.012 * h["spikiness"] * s, smooth=False)

        def keep_fade(c):
            return 1.618 * s < c.z <= 1.74 * s and c.y > -0.012 * s

        shell("hair_fade", keep_fade, lambda c: 0.0016, "fade")
    elif style == "buzz":
        shell("hair_top", lambda c: c.z > 1.66 * s and c.y > -0.07 * s, lambda c: 0.003, "hair")
    # other styles plug in here (see README: hair registry)


def build_glasses(B, surf, cfg, s):
    g = cfg["glasses"]
    if g["style"] != "rect_fullrim":
        return
    ez, ex = 1.683 * s, 0.031 * s
    w, h, t = 0.056 * s, 0.032 * s, 0.0032
    # sit the front of the frame in front of the most forward face point under the lenses
    ys = [surf(x * s, z * s).y for x in (-0.06, -0.03, 0.0, 0.03, 0.06) for z in (1.665, 1.683, 1.70)]
    fy = min(ys) - 0.009
    for sx, side in ((1, "L"), (-1, "R")):
        cx = ex * sx + 0.002 * sx
        for k, (dx, dz, sw, sh) in enumerate(((0, h / 2, w, t), (0, -h / 2, w, t), (w / 2, 0, t, h), (-w / 2, 0, t, h))):
            B.box(f"glasses_rim{k}_{side}", Vector((cx + dx, fy, ez + dz)), (sw, 0.0035, sh), "frame", "Head")
        B.box(f"glasses_lens_{side}", Vector((cx, fy + 0.0005, ez)), (w - t, 0.0018, h - t), "lens", "Head")
        # hinge + temple running back to the ear, sitting outside the head
        hx = cx + (w / 2) * sx
        B.box(f"glasses_hinge_{side}", Vector((hx + 0.003 * sx, fy + 0.006, ez + h / 2 - 0.006)), (0.007, 0.014, 0.008), "frame", "Head")
        a = Vector((hx + 0.004 * sx, fy + 0.012, ez + h / 2 - 0.007))
        b_ = Vector(((0.09 * cfg["face"]["head_width"] * s + 0.004) * sx, 0.012 * s, 1.678 * s))
        mid = (a + b_) / 2
        d = b_ - a
        rot = Vector((0, 1, 0)).rotation_difference(d.normalized()).to_matrix()
        B.box(f"glasses_temple_{side}", mid, (0.0035, d.length, 0.0045), "frame", "Head", rot=rot)
    B.box("glasses_bridge", Vector((0, fy, ez + 0.009)), (0.012 * s, 0.004, 0.0035), "frame", "Head")
    for sx, side in ((1, "L"), (-1, "R")):
        B.box(f"glasses_pad_{side}", Vector((0.009 * sx * s, fy + 0.006, ez - 0.004)), (0.004, 0.006, 0.008), "frame", "Head")


def build_accessories(B, P, s):
    for a in B.cfg["accessories"]:
        if a["type"] != "watch":
            continue
        side = a.get("side", "L")
        el, wr = P[f"elbow_{side}"], P[f"wrist_{side}"]
        d = (wr - el).normalized()
        u, v = frame_along(d)
        c = wr - d * 0.03 * s
        out = u if side == "L" else -u      # back of the wrist (outer side in A-pose / hanging pose)
        if out.z < 0:
            out = -out
        B.loft(f"watch_band_{side}", [(c - d * 0.011 * s, u, v, 0.0345 * s, 0.031 * s, 2.0), (c + d * 0.011 * s, u, v, 0.0345 * s, 0.031 * s, 2.0)],
               "steel", f"Forearm.{side}", segs=16, subdiv=0)
        rot = Vector((0, 0, 1)).rotation_difference(out).to_matrix()
        cc = c + out * 0.036 * s
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.019 * s, radius2=0.019 * s, depth=0.009)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(cc) @ rot.to_4x4(), verts=bm.verts)
        B.obj(f"watch_case_{side}", bm, "steel", f"Forearm.{side}", smooth=False)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.0155 * s, radius2=0.0155 * s, depth=0.0015)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(cc + out * 0.0048) @ rot.to_4x4(), verts=bm.verts)
        B.obj(f"watch_dial_{side}", bm, "dial", f"Forearm.{side}", smooth=False)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.0205 * s, radius2=0.0185 * s, depth=0.0025)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(cc + out * 0.0055) @ rot.to_4x4(), verts=bm.verts)
        B.obj(f"watch_bezel_{side}", bm, "steel", f"Forearm.{side}", smooth=False)


# --------------------------------------------------------------------------- poses

def rot_bone(arm, name, axis, deg):
    """Rotate a pose bone about an armature-space axis (through the bone head)."""
    pb = arm.pose.bones[name]
    pb.rotation_mode = "QUATERNION"
    Bm = pb.bone.matrix_local.to_3x3()
    R = Matrix.Rotation(math.radians(deg), 3, Vector(axis))
    q = (Bm.inverted() @ R @ Bm).to_quaternion()
    pb.rotation_quaternion = q @ pb.rotation_quaternion


POSES = {
    "neutral": [],                                                      # rest A-pose
    "relaxed": [("UpperArm.L", (0, 1, 0), 24), ("UpperArm.R", (0, 1, 0), -24),
                ("Forearm.L", (1, 0, 0), -14), ("Forearm.R", (1, 0, 0), -14),
                ("Hand.L", (1, 0, 0), -6), ("Hand.R", (1, 0, 0), -6),
                ("Head", (1, 0, 0), -3)],
    "test_arms": [("UpperArm.L", (0, 1, 0), -63), ("Forearm.L", (1, 0, 0), -80),
                  ("UpperArm.R", (1, 0, 0), -70), ("Forearm.R", (0, 1, 0), -60)],
    "test_head_legs": [("Head", (0, 0, 1), 40), ("Neck", (1, 0, 0), 12),
                       ("Thigh.L", (1, 0, 0), -55), ("Shin.L", (1, 0, 0), 75), ("Foot.L", (1, 0, 0), -15),
                       ("Thigh.R", (1, 0, 0), 20), ("Spine", (0, 0, 1), 15)],
}


def apply_pose(arm, name):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    for bn, axis, deg in POSES[name]:
        rot_bone(arm, bn, axis, deg)
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------- build entry point

REQUIRED_ROLES = ["head", "hair_top", "eye_L", "eye_R", "brow_L", "brow_R", "nose_tip", "mouth_line", "ear_L", "ear_R",
                  "glasses_lens_L", "glasses_lens_R", "glasses_temple_L", "glasses_bridge", "neck",
                  "shirt_torso", "collar_L", "collar_R", "collar_band", "sleeve_L", "sleeve_R", "forearm_L", "forearm_R", "palm_L", "palm_R",
                  "thumb_L", "finger0_L", "trousers_seat", "leg_L", "leg_R", "shoe_L", "shoe_R", "sole_L", "watch_case_L"]


def build_avatar(cfg, collection_name, prefix):
    cfg = merge(DEFAULT_CONFIG, cfg)
    old = bpy.data.collections.get(collection_name)
    if old:
        datas = []
        for ob in list(old.all_objects):
            if ob.data is not None:
                datas.append(ob.data)
            bpy.data.objects.remove(ob, do_unlink=True)
        for d in datas:                       # drop orphan meshes / armatures / cameras so names stay clean
            if d.users == 0:
                for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.cameras):
                    if d.name in coll and coll[d.name] == d:
                        coll.remove(d)
                        break
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(col)
    col["resident_id"] = cfg["id"]
    col["display_name"] = cfg["display_name"]
    mats = make_materials(cfg, prefix)
    B = Builder(cfg, col, mats, prefix)
    P, s = skeleton_points(cfg)
    build_body(B, P, s)
    head, bvh, surf = build_head(B, P, s)
    build_hair(B, head, cfg, s)
    build_glasses(B, surf, cfg, s)
    build_accessories(B, P, s)
    arm = build_armature(f"{prefix}_Rig", col, P, s)
    skin(B, arm)
    return arm, B, cfg


def place(arm, location, rot_z_deg=0.0):
    arm.location = Vector(location)
    arm.rotation_euler = (0, 0, math.radians(rot_z_deg))
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------- validation

def eval_mesh_world(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = ob.evaluated_get(dg)
    me = eo.to_mesh()
    vs = [eo.matrix_world @ v.co for v in me.vertices]
    edges = [tuple(e.vertices) for e in me.edges]
    eo.to_mesh_clear()
    return vs, edges


def bvh_world(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = ob.evaluated_get(dg)
    me = eo.to_mesh()
    vs = [eo.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    return BVHTree.FromPolygons(vs, polys)


def inside_count(points, bvh):
    inside, min_d = 0, 1e9
    for p in points:
        loc, n, _i, d = bvh.find_nearest(p)
        if loc is None:
            continue
        if (p - loc).dot(n) < 0:
            inside += 1
        min_d = min(min_d, d)
    return inside, min_d


def validate_avatar(arm, B):
    rep = {}
    parts = B.parts
    rep["missing_parts"] = [r for r in REQUIRED_ROLES if r not in parts]
    rep["mesh_parts"] = len(parts)
    rep["bones"] = [b.name for b in arm.data.bones]
    rep["all_parts_rigged"] = all(any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers) and o.vertex_groups for o in parts.values())
    apply_pose(arm, "neutral")
    # scale
    zs = [v.z for o in parts.values() for v in eval_mesh_world(o)[0]]
    rep["height_m"] = round(max(zs) - min(zs), 3)
    rep["feet_min_z_local"] = round(min(zs) - arm.location.z, 4)
    # glasses vs face
    hb = bvh_world(parts["head"])
    gl = [v for r, o in parts.items() if r.startswith("glasses") for v in eval_mesh_world(o)[0]]
    ins, mind = inside_count(gl, hb)
    rep["glasses_vertices_inside_head"] = ins
    rep["glasses_min_clearance_mm"] = round(mind * 1000, 1)
    # hair is outside the skull
    hv = [v for r in ("hair_top", "hair_fade") if r in parts for v in eval_mesh_world(parts[r])[0]]
    rep["hair_vertices_inside_head"] = inside_count(hv, hb)[0]
    # clothing vs body: trouser waist stays under the shirt, forearm skin stays inside sleeve/cuff
    sb = bvh_world(parts["shirt_torso"])
    tw = [v for v in eval_mesh_world(parts["trousers_seat"])[0] if v.z - arm.location.z > 0.86 * B.cfg["height"] / 1.78]
    rep["trouser_waist_poking_through_shirt"] = len(tw) - inside_count(tw, sb)[0]
    hem = 0.885 * B.cfg["height"] / 1.78
    lv = [v for k in ("L", "R") for v in eval_mesh_world(parts[f"leg_{k}"])[0] if v.z - arm.location.z > hem]
    rep["trouser_legs_poking_through_shirt"] = len(lv) - inside_count(lv, sb)[0]
    poke = 0
    for side in ("L", "R"):
        cb = bvh_world(parts[f"cuff_{side}"])
        slb = bvh_world(parts[f"sleeve_{side}"])
        fv = eval_mesh_world(parts[f"forearm_{side}"])[0][:12]          # first ring(s) = inside the rolled cuff
        for p in fv:
            l1, n1, _, d1 = cb.find_nearest(p)
            l2, n2, _, d2 = slb.find_nearest(p)
            l, n = (l1, n1) if d1 < d2 else (l2, n2)
            poke += (p - l).dot(n) > 0
    rep["forearm_skin_poking_through_sleeves"] = poke
    # deformation test poses: worst edge stretch vs rest
    rest = {r: eval_mesh_world(o) for r, o in parts.items()}
    worst = {}
    for pose in ("test_arms", "test_head_legs", "relaxed"):
        apply_pose(arm, pose)
        mx = 0.0
        where = ""
        for r, o in parts.items():
            vs, edges = eval_mesh_world(o)
            rv, _ = rest[r]
            for a, b in edges:
                l0 = (rv[a] - rv[b]).length
                if l0 > 1e-5:
                    k = (vs[a] - vs[b]).length / l0
                    if k > mx:
                        mx, where = k, r
        worst[pose] = (round(mx, 2), where)
    rep["max_edge_stretch_by_pose"] = worst
    apply_pose(arm, "neutral")
    return rep
