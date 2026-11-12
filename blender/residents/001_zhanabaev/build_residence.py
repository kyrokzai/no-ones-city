"""NO ONE'S CITY — Resident #001: FOUNDER RESIDENCE 001 (M0.6).

Resident:   #001  (Instagram @zhanabaev.d.d)
Plot ID:    NOC-001
Style:      Modern Low-Poly x Premium Contemporary Architecture x Cozy Cinematic

A reusable, self-contained residence module for the NO ONE'S CITY district:
  * everything lives in the collection RESIDENT_001_FOUNDER_RESIDENCE (+ sub-collections)
  * every object is parented to the empty RES001_Root -> move / rotate the root to move the whole estate
  * all materials are prefixed RES001_ and listed in MATERIALS -> recolour without touching geometry
  * fully designed on all four sides + roof (no one-sided stage set)

Modes:
  city (default)   open the M0.5/M0.4 city scene, clear the founder plot, build the residence,
                   add cameras, validate, save the city scene
  --standalone     build a separate scene: residence + ground + waterfront + sky, same coordinates

    python build_residence.py --city ../../episode-001/scenes/noc_ep001_district.blend \
        --save ../../episode-001/scenes/noc_ep001_district.blend --renders renders
    python build_residence.py --standalone --save scenes/resident_001_founder_residence.blend

Works with Blender 4.x (`blender -b -P build_residence.py -- ...`) or the `bpy` module.
"""

import argparse
import math
import os
import sys
from types import SimpleNamespace

import bpy  # noqa: F401  (must come before bmesh users when used as a module)
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "episode-001", "scripts")))
import build_district as bd  # noqa: E402  (shared low-poly helpers, palette, sky, lights)

# --------------------------------------------------------------------------- identity & plot

RESIDENT = {
    "resident_id": "#001",
    "instagram": "@zhanabaev.d.d",
    "plot_id": "NOC-001",
    "house_name": "Founder Residence 001",
    "sign_lines": ["FOUNDER #001", "ZHANABAEV", "NOC-001"],
}
COLLECTION = "RESIDENT_001_FOUNDER_RESIDENCE"
PREFIX = "RES001"

# founder plot on the first waterfront line, east of East Street:
#   south edge on the Cross Street sidewalk (y 5.7), north edge 0.6 m short of the public promenade (y 36.2)
PLOT_CENTER = Vector((60.5, 20.8, 0.0))
PLOT_HALF = (14.0, 14.8)               # local x: -14..14, local y: -14.8..14.8  (+Y = north / water)
PROMENADE_Y = 36.2

# --------------------------------------------------------------------------- materials (swap freely)

MATERIALS = {
    # name: (kind, args)
    "concrete": ("tex", ("#cfc9bf", "#c6bfb4", "#a89f92", 1.5, 0.75, 0.005, 0.75, True)),
    "graphite": ("flat", ("#2b2e35", 0.6, 0.15)),
    "wood": ("tex", ("#b5784a", "#a0663b", "#4a2c18", 0.14, 30.0, 0.022, 0.55, True)),
    "wood_soffit": ("tex", ("#a8703f", "#97603a", "#4a2c18", 30.0, 0.14, 0.02, 0.6, False)),
    "deck": ("tex", ("#8f5d3b", "#7f5032", "#3b2416", 2.4, 0.16, 0.012, 0.7, False)),
    "pavers": ("tex", ("#c8bcaa", "#bcae9a", "#8e8272", 0.8, 0.4, 0.01, 0.75, False)),
    "glass_dark": ("flat", ("#18263a", 0.04, 0.0, 0.95)),
    "glass_lit": ("emit", ("#ffb46a", "#ffa452", 1.6, 0.2)),
    "glass_rail": ("flat", ("#9cb8cf", 0.05, 0.0, 0.9)),
    "metal": ("flat", ("#5e626a", 0.55, 0.55)),
    "led": ("emit", ("#ffd39a", "#ffbe72", 7.0, 0.3)),
    "uplight": ("emit", ("#ffd9a0", "#ffbf6a", 10.0, 0.3)),
    "pool": ("emit", ("#1f9fb0", "#45d0de", 0.8, 0.03)),
    "pool_tile": ("flat", ("#16606e", 0.2, 0.0)),
    "fire": ("emit", ("#ff8a3a", "#ff7a22", 12.0, 0.4)),
    "cushion": ("flat", ("#ece6dc", 0.85, 0.0)),
    "solar": ("flat", ("#1b2a4a", 0.12, 0.4, 0.9)),
    "green_wall": ("flat", ("#3f6b33", 0.9, 0.0)),
    "lawn": ("flat", ("#62873a", 0.8, 0.0)),
    "sign_gold": ("emit", ("#f2c46a", "#ffbf55", 9.0, 0.3)),
}


def build_materials():
    out = {}
    for key, (kind, a) in MATERIALS.items():
        name = f"{PREFIX}_{key}"
        if name in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[name])
        bd.MATS.pop(name, None)
        if kind == "tex":
            c1, c2, mort, bw, rh, ms, rough, facade = a
            out[key] = bd.tex_mat(name, c1, c2, mort, bw, rh, ms, rough, facade=facade)
        elif kind == "emit":
            col, emit, strength, rough = a
            out[key] = bd.mat(name, col, rough, emit=emit, strength=strength)
        else:
            col, rough, metallic = a[0], a[1], a[2]
            spec = a[3] if len(a) > 3 else 0.5
            out[key] = bd.mat(name, col, rough, metallic=metallic, spec=spec)
    return out


# --------------------------------------------------------------------------- builder

class Residence:
    """Builds the estate in local coordinates under RES001_Root (identity while building)."""

    def __init__(self, mats):
        self.m = mats
        parent = bpy.data.collections.get(COLLECTION)
        if parent:
            for ob in list(parent.all_objects):
                bpy.data.objects.remove(ob, do_unlink=True)
            for ch in list(parent.children_recursive):
                bpy.data.collections.remove(ch)
            bpy.data.collections.remove(parent)
        self.col = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(self.col)
        for k, v in RESIDENT.items():
            self.col[k] = v if not isinstance(v, list) else " / ".join(v)
        self.sub = {}
        for name in ("House", "Terraces", "Landscape", "Sign", "Lights", "Cameras"):
            c = bpy.data.collections.new(f"{COLLECTION}_{name}")
            self.col.children.link(c)
            self.sub[name] = c
        self.root = bpy.data.objects.new(f"{PREFIX}_Root", None)
        self.root.empty_display_type = "ARROWS"
        self.root.empty_display_size = 3
        self.col.objects.link(self.root)
        self.n = 0

    # -- primitives (all parented to the root, local coordinates)
    def _name(self, n):
        self.n += 1
        return f"{PREFIX}_{n}"

    def box(self, n, size, loc, mat, sub="House", rot=(0, 0, 0)):
        ob = bd.box(self._name(n), size, loc, self.m[mat] if isinstance(mat, str) else mat, self.sub[sub], parent=self.root)
        ob.rotation_euler = rot
        return ob

    def span(self, n, x0, x1, y0, y1, z0, z1, mat, sub="House"):
        return self.box(n, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, z0), mat, sub)

    def cyl(self, n, r1, r2, h, segs, loc, mat, sub="House"):
        return bd.cyl(self._name(n), r1, r2, h, segs, loc, self.m[mat], self.sub[sub], parent=self.root)

    def light(self, n, loc, color, energy, radius=0.5):
        l = bpy.data.lights.new(self._name(n), "POINT")
        l.color = bd.srgb(color)
        l.energy = energy
        l.shadow_soft_size = radius
        ob = bpy.data.objects.new(l.name, l)
        self.sub["Lights"].objects.link(ob)
        ob.parent = self.root
        ob.location = loc
        return ob

    def adopt(self, objs, sub="Landscape"):
        for ob in objs:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            self.sub[sub].objects.link(ob)
            ob.parent = self.root

    def tree(self, n, loc, shape, size):
        before = set(bpy.data.objects)
        bd.tree(self._name(n), loc, size=size, shape=shape, c=self.sub["Landscape"])
        self.adopt(set(bpy.data.objects) - before)

    def shrub(self, n, loc, r=0.45):
        self.adopt([bd.shrub(self._name(n), loc, r, self.sub["Landscape"])])

    # -- facade elements
    def glazing(self, n, axis, at, a0, a1, z0, h, panes, out, lit=0.7, sub="House"):
        """Framed floor-to-ceiling glazing on a facade plane.
        axis 'x': facade normal along +/-Y at y=at, spanning x a0..a1;  axis 'y': normal along +/-X at x=at.
        out = +1/-1: which side the facade faces (frames sit on that side)."""
        w = (a1 - a0) / panes
        for i in range(panes):
            c = a0 + (i + 0.5) * w
            mat = "glass_lit" if (i * 7 + self.n) % 10 < lit * 10 else "glass_dark"
            if axis == "x":
                self.box(f"{n}_pane{i}", (w, 0.06, h), (c, at + out * 0.03, z0), mat, sub)
            else:
                self.box(f"{n}_pane{i}", (0.06, w, h), (at + out * 0.03, c, z0), mat, sub)
        for i in range(panes + 1):
            c = a0 + i * w
            if axis == "x":
                self.box(f"{n}_mull{i}", (0.07, 0.14, h), (c, at + out * 0.07, z0), "metal", sub)
            else:
                self.box(f"{n}_mull{i}", (0.14, 0.07, h), (at + out * 0.07, c, z0), "metal", sub)
        for zz, hh in ((z0 - 0.02, 0.08), (z0 + h - 0.06, 0.1)):
            if axis == "x":
                self.box(f"{n}_rail{zz:.1f}", (a1 - a0 + 0.1, 0.16, hh), ((a0 + a1) / 2, at + out * 0.08, zz), "metal", sub)
            else:
                self.box(f"{n}_rail{zz:.1f}", (0.16, a1 - a0 + 0.1, hh), (at + out * 0.08, (a0 + a1) / 2, zz), "metal", sub)

    def parapet(self, n, x0, x1, y0, y1, z, h=0.42, t=0.22, mat="graphite", skip=()):
        """Flat-roof parapet with a matte-metal coping on four edges ('n','s','e','w' in skip are left open)."""
        edges = {"s": (x0, x1, y0, y0 + t), "n": (x0, x1, y1 - t, y1), "w": (x0, x0 + t, y0 + t, y1 - t), "e": (x1 - t, x1, y0 + t, y1 - t)}
        for k, (a, b, c, d) in edges.items():
            if k in skip:
                continue
            self.span(f"{n}_par{k}", a, b, c, d, z, z + h, mat)
            self.span(f"{n}_cap{k}", a - 0.02, b + 0.02, c - 0.02, d + 0.02, z + h, z + h + 0.05, "metal")

    def glass_rail(self, n, x0, x1, y0, y1, z, sub="Terraces"):
        """Frameless glass balustrade with a slim metal handrail along a straight run."""
        if abs(y1 - y0) < 1e-6:
            self.span(f"{n}_g", x0, x1, y0 - 0.02, y0 + 0.02, z, z + 1.0, "glass_rail", sub)
            self.span(f"{n}_h", x0, x1, y0 - 0.04, y0 + 0.04, z + 1.0, z + 1.05, "metal", sub)
        else:
            self.span(f"{n}_g", x0 - 0.02, x0 + 0.02, y0, y1, z, z + 1.0, "glass_rail", sub)
            self.span(f"{n}_h", x0 - 0.04, x0 + 0.04, y0, y1, z + 1.0, z + 1.05, "metal", sub)

    def slats(self, n, axis, at, a0, a1, z0, h, step=0.32, depth=0.16, out=1):
        """Vertical timber fins (brise-soleil) in front of a facade."""
        k = int((a1 - a0) / step)
        for i in range(k + 1):
            c = a0 + i * (a1 - a0) / max(k, 1)
            if axis == "x":
                self.box(f"{n}_fin{i}", (0.07, depth, h), (c, at + out * (depth / 2 + 0.05), z0), "wood")
            else:
                self.box(f"{n}_fin{i}", (depth, 0.07, h), (at + out * (depth / 2 + 0.05), c, z0), "wood")

    def uplights(self, n, pts):
        for i, (x, y) in enumerate(pts):
            self.cyl(f"{n}_{i}", 0.09, 0.09, 0.08, 8, (x, y, G), "uplight", "Landscape")


G = 0.1           # plot ground level (top of the lawn base)
Z0 = 0.22         # finished ground floor (plinth top)
H1 = 3.4          # ground floor height
Z1 = Z0 + H1      # first floor slab
H2 = 3.2          # first floor height
Z2 = Z1 + H2      # main roof


def build_estate(r):
    """Founder Residence 001. Local frame: +Y north (lake), -Y south (Cross Street, entrance)."""
    hx, hy = PLOT_HALF
    # ---------------------------------------------------------------- plot, boundary, drive
    r.span("Plot_Lawn", -hx, hx, -hy, hy, 0.0, G, "lawn", "Landscape")
    r.span("Forecourt", -14.0, -2.0, -hy, -6.2, G, G + 0.03, "pavers", "Landscape")
    r.span("Drive_Apron", -12.4, -8.6, -hy - 0.3, -hy, 0.0, G + 0.03, "pavers", "Landscape")   # crosses the verge to the sidewalk
    r.span("Entry_Walk", -1.6, 1.6, -hy, -6.6, G, G + 0.04, "pavers", "Landscape")
    for k in range(3):
        r.span(f"Entry_Step{k}", -1.9, 1.9, -6.6 + k * 0.45, -6.15 + k * 0.45, G, G + 0.04 + (k + 1) * 0.04, "concrete", "Landscape")
    # boundary: low concrete wall + clipped hedge, openings for the drive, the entry walk and the lake gate
    for a, b in ((-14.0, -12.6), (-8.4, -7.6), (-3.2, -1.8), (1.8, 14.0)):     # gaps: drive, sign bay, entry
        r.span(f"Wall_S_{a:.0f}", a, b, -hy, -hy + 0.3, G, G + 0.55, "concrete", "Landscape")
        r.span(f"Hedge_S_{a:.0f}", a, b, -hy + 0.35, -hy + 0.95, G, G + 1.0, "green_wall", "Landscape")
    for sx in (-1, 1):
        r.span(f"Hedge_{sx}", sx * hx - (0.6 if sx > 0 else 0), sx * hx + (0.6 if sx < 0 else 0), -hy + 1.0, hy - 0.4, G, G + 1.2, "green_wall", "Landscape")
    for a, b in ((-hx, -1.2), (1.2, hx)):
        r.span(f"Hedge_N_{a:.0f}", a, b, hy - 0.6, hy - 0.05, G, G + 0.8, "green_wall", "Landscape")
    r.span("LakeGate_Path", -1.2, 1.2, 11.2, hy + PROMENADE_Y - (PLOT_CENTER.y + hy) - 0.01, G, G + 0.03, "pavers", "Landscape")
    for sx in (-1, 1):
        r.span(f"LakeGate_Post{sx}", sx * 1.2 - 0.12, sx * 1.2 + 0.12, hy - 0.6, hy - 0.05, G, G + 1.1, "graphite", "Landscape")
        r.cyl(f"LakeGate_Light{sx}", 0.06, 0.06, 0.05, 8, (sx * 1.2, hy - 0.33, G + 1.1), "uplight", "Landscape")

    # ---------------------------------------------------------------- A: ground floor, light architectural concrete
    r.span("Plinth", -8.3, 8.3, -5.3, 5.3, G, Z0, "concrete")
    r.span("A_Body", -8.0, 8.0, -5.0, 5.0, Z0, Z1, "concrete")
    r.glazing("A_North", "x", 5.0, -7.8, 7.8, Z0 + 0.05, H1 - 0.35, 8, +1)                 # lake: full width
    r.glazing("A_East", "y", 8.0, -4.7, 4.7, Z0 + 0.05, H1 - 0.35, 4, +1)                  # garden dining
    r.glazing("A_West", "y", -8.0, 1.3, 4.7, Z0 + 0.05, H1 - 0.35, 2, -1)                  # beside the garage
    r.glazing("A_South_E", "x", -5.0, 4.8, 7.8, Z0 + 0.05, H1 - 0.35, 2, -1)
    r.glazing("A_South_Clerestory", "x", -5.0, -7.6, -2.4, Z0 + 2.3, 0.75, 4, -1)
    r.span("A_South_WoodPanel", -7.6, -2.4, -5.18, -5.0, Z0, Z0 + 2.2, "wood")
    # entrance: tall pivot door, side lights, cantilevered canopy with LED, house name
    r.span("Door", -0.8, 0.8, -5.12, -5.0, Z0, Z0 + 2.9, "wood")
    r.span("Door_Frame", -1.0, 1.0, -5.18, -5.05, Z0 + 2.9, Z0 + 3.05, "metal")
    for sx in (-1, 1):
        r.span(f"Door_Side{sx}", sx * 0.85 - 0.12, sx * 0.85 + 0.12, -5.12, -5.0, Z0, Z0 + 2.9, "glass_lit")
    r.span("Canopy", -3.2, 1.4, -8.4, -5.0, Z0 + 3.0, Z0 + 3.2, "graphite")
    r.span("Canopy_Soffit", -3.1, 1.3, -8.3, -5.05, Z0 + 2.97, Z0 + 3.0, "wood_soffit")
    r.span("Canopy_LED", -3.0, 1.2, -8.32, -8.24, Z0 + 2.93, Z0 + 2.97, "led")
    r.span("Canopy_Column", -3.05, -2.85, -8.25, -8.05, Z0, Z0 + 3.0, "metal")
    r.light("Entrance_Light", (-0.8, -6.8, Z0 + 2.6), "#ffc27a", 180, 0.6)

    # ---------------------------------------------------------------- B: massive graphite first floor, cantilevered
    bx0, bx1, by0, by1 = -5.0, 12.0, -3.5, 7.5     # 4 m over the east garden, 2.5 m over the lake terrace
    r.span("B_Slab", bx0, bx1, by0, by1, Z1, Z1 + 0.3, "graphite")
    r.span("B_Body", bx0, bx1, by0, by1, Z1 + 0.3, Z2, "graphite")
    r.glazing("B_North", "x", by1, bx0 + 0.3, bx1 - 0.3, Z1 + 0.45, H2 - 0.65, 9, +1)
    r.glazing("B_East", "y", bx1, by0 + 0.3, by1 - 0.3, Z1 + 0.45, H2 - 0.65, 5, +1)
    r.glazing("B_West", "y", bx0, by0 + 0.4, by1 - 0.4, Z1 + 0.45, H2 - 0.65, 4, -1)
    r.glazing("B_South_Ribbon", "x", by0, bx0 + 0.5, bx1 - 0.5, Z1 + 1.35, 1.2, 10, -1)
    r.slats("B_South_Fins", "x", by0, bx0 + 0.4, bx1 - 0.4, Z1 + 0.3, H2 - 0.3, step=0.6, out=-1)
    # undersides of the cantilevers: timber soffit + LED wash
    r.span("B_Soffit_E", 8.0, bx1, by0, by1, Z1 - 0.03, Z1, "wood_soffit")
    r.span("B_Soffit_N", bx0, 8.0, 5.0, by1, Z1 - 0.03, Z1, "wood_soffit")
    r.span("B_LED_N", bx0 + 0.2, bx1 - 0.2, by1 - 0.3, by1 - 0.22, Z1 - 0.07, Z1 - 0.03, "led")
    r.span("B_LED_E", bx1 - 0.3, bx1 - 0.22, by0 + 0.2, by1 - 0.2, Z1 - 0.07, Z1 - 0.03, "led")
    # lake balcony along the whole north face
    r.span("B_Balcony", bx0, bx1, by1, by1 + 1.6, Z1, Z1 + 0.25, "graphite", "Terraces")
    r.span("B_Balcony_Deck", bx0 + 0.05, bx1 - 0.05, by1, by1 + 1.55, Z1 + 0.25, Z1 + 0.28, "deck", "Terraces")
    r.glass_rail("B_Balcony_Rail", bx0, bx1, by1 + 1.55, by1 + 1.55, Z1 + 0.28)
    r.span("B_Balcony_LED", bx0 + 0.2, bx1 - 0.2, by1 + 1.45, by1 + 1.52, Z1 - 0.04, Z1, "led", "Terraces")
    r.parapet("B_Roof", bx0, bx1, by0, by1, Z2)
    r.span("B_Roof_Gravel", bx0 + 0.22, bx1 - 0.22, by0 + 0.22, by1 - 0.22, Z2, Z2 + 0.05, "metal")
    # technology on the roof: solar array + skylight
    for row in range(2):
        for k in range(6):
            p = r.box(f"Solar_{row}_{k}", (1.9, 1.1, 0.06), (0.5 + k * 2.0, 1.0 + row * 2.6, Z2 + 0.35), "solar")
            p.rotation_euler.x = math.radians(-18)
            r.span(f"Solar_Leg_{row}_{k}", 0.4 + k * 2.0, 0.6 + k * 2.0, 1.2 + row * 2.6, 1.4 + row * 2.6, Z2 + 0.05, Z2 + 0.4, "metal")
    r.span("Skylight", -3.6, -1.0, 0.5, 4.5, Z2 + 0.05, Z2 + 0.4, "glass_lit")

    # ---------------------------------------------------------------- C: timber stair tower beside the entrance
    r.span("C_Tower", 1.6, 4.6, -6.2, -3.4, Z0, Z2 + 0.8, "wood")
    for i, x in enumerate((2.3, 3.9)):
        r.span(f"C_Slot{i}", x - 0.18, x + 0.18, -6.26, -6.2, Z0 + 0.6, Z2 + 0.2, "glass_lit")
    r.span("C_Cap", 1.5, 4.7, -6.3, -3.3, Z2 + 0.8, Z2 + 0.9, "metal")
    r.span("C_Glass_E", 4.6, 4.66, -5.9, -3.7, Z1 + 0.5, Z2, "glass_dark")
    r.span("C_Glass_W", 1.54, 1.6, -5.9, -3.7, Z0 + 0.5, Z1 - 0.3, "glass_lit")

    # ---------------------------------------------------------------- D: two-car garage + roof terrace
    gx0, gx1, gy0, gy1 = -13.0, -7.9, -6.0, 1.0
    r.span("D_Garage", gx0, gx1, gy0, gy1, Z0 - 0.1, Z1, "graphite")
    for i, cx in enumerate((-11.75, -9.2)):
        r.span(f"D_Door{i}", cx - 1.15, cx + 1.15, gy0 - 0.08, gy0, Z0 - 0.1, Z0 + 2.3, "wood")
        r.span(f"D_DoorLED{i}", cx - 1.1, cx + 1.1, gy0 - 0.16, gy0 - 0.1, Z0 + 2.42, Z0 + 2.46, "led")
    r.span("D_Header", gx0, gx1, gy0 - 0.25, gy0, Z0 + 2.3, Z1, "graphite")
    r.span("D_GreenWall", gx0 - 0.22, gx0, gy0 + 0.6, gy1 - 0.6, Z0 + 0.3, Z1 - 0.3, "green_wall")      # west: vertical garden
    r.span("D_GreenWall_Frame", gx0 - 0.26, gx0 - 0.2, gy0 + 0.5, gy1 - 0.5, Z1 - 0.32, Z1 - 0.26, "metal")
    r.glazing("D_North", "x", gy1, gx0 + 0.4, gx1 - 0.2, Z0 + 0.4, 1.0, 3, +1, lit=0.4)       # high windows to the lounge
    # roof terrace over garage + west strip of A, deck + glass rail + planters
    r.span("RoofTerrace_Deck", gx0 + 0.1, bx0, gy0 + 0.1, 5.0 - 0.1, Z1, Z1 + 0.06, "deck", "Terraces")
    r.glass_rail("RT_Rail_S", gx0, bx0, gy0 + 0.05, gy0 + 0.05, Z1 + 0.06)
    r.glass_rail("RT_Rail_W", gx0 + 0.05, gx0 + 0.05, gy0, 5.0, Z1 + 0.06)
    r.glass_rail("RT_Rail_N", gx0, bx0, 4.95, 4.95, Z1 + 0.06)
    r.glass_rail("RT_Rail_N2", -8.0, bx0, -4.95, -4.95, Z1 + 0.06)
    for i, (x, y) in enumerate(((-12.2, -3.0), (-12.2, 0.5), (-9.0, 3.8))):
        r.span(f"RT_Planter{i}", x - 0.5, x + 0.5, y - 0.5, y + 0.5, Z1 + 0.06, Z1 + 0.6, "graphite", "Terraces")
        r.shrub(f"RT_Plant{i}", (x, y, Z1 + 0.6), 0.45)
    for k in range(2):   # outdoor seating on the roof terrace
        r.span(f"RT_Seat{k}", -11.8 + k * 2.2, -10.4 + k * 2.2, 1.6, 2.4, Z1 + 0.06, Z1 + 0.5, "cushion", "Terraces")
    # strip of A roof south of B: deck + rail
    r.span("A_RoofSouth_Deck", bx0, 8.0, -5.0 + 0.1, by0, Z1, Z1 + 0.06, "deck", "Terraces")
    r.glass_rail("A_RoofSouth_Rail", bx0, 1.6, -4.95, -4.95, Z1 + 0.06)
    r.glass_rail("A_RoofSouth_RailE", 4.6, 8.0, -4.95, -4.95, Z1 + 0.06)
    r.glass_rail("A_RoofEast_Rail", 7.95, 7.95, -5.0, by0, Z1 + 0.06)

    # ---------------------------------------------------------------- lake side: terrace, pool, lounge
    TZ = G + 0.32     # terrace top
    px0, px1, py0, py1 = 0.6, 11.6, 7.6, 10.6
    for n, (a, b, c, d) in {"T_West": (-8.0, px0, 5.0, 11.2), "T_East": (px1, 13.2, 5.0, 11.2),
                            "T_South": (px0, px1, 5.0, py0), "T_North": (px0, px1, py1, 11.2)}.items():
        r.span(n, a, b, c, d, G, TZ, "deck", "Terraces")
    r.span("Pool_Basin", px0, px1, py0, py1, G - 0.05, TZ - 0.12, "pool_tile", "Terraces")
    r.span("Pool_Water", px0, px1, py0, py1, TZ - 0.12, TZ - 0.06, "pool", "Terraces")
    for n, (a, b, c, d) in {"S": (px0 - 0.3, px1 + 0.3, py0 - 0.3, py0), "N": (px0 - 0.3, px1 + 0.3, py1, py1 + 0.3),
                            "W": (px0 - 0.3, px0, py0, py1), "E": (px1, px1 + 0.3, py0, py1)}.items():
        r.span(f"Pool_Coping_{n}", a, b, c, d, TZ, TZ + 0.04, "concrete", "Terraces")
    r.span("Pool_LED", px0 + 0.3, px1 - 0.3, py0 + 0.02, py0 + 0.08, TZ - 0.2, TZ - 0.07, "led", "Terraces")
    r.light("Pool_Glow", ((px0 + px1) / 2, (py0 + py1) / 2, TZ + 0.4), "#7fe6f0", 220, 2.0)
    for k in range(4):   # sun loungers along the pool
        x = 2.0 + k * 2.6
        r.span(f"Lounger{k}", x - 0.4, x + 0.4, 5.4, 7.2, TZ, TZ + 0.3, "wood", "Terraces")
        r.box(f"Lounger{k}_Back", (0.78, 0.6, 0.08), (x, 5.75, TZ + 0.3), "cushion", "Terraces", rot=(math.radians(35), 0, 0))
        r.span(f"Lounger{k}_Pad", x - 0.38, x + 0.38, 6.05, 7.15, TZ + 0.3, TZ + 0.36, "cushion", "Terraces")
    # lounge with fire table under a slatted pergola (west of the pool)
    r.span("Sofa_L1", -7.6, -2.0, 9.6, 10.6, TZ, TZ + 0.45, "graphite", "Terraces")
    r.span("Sofa_L1_Cushion", -7.5, -2.1, 9.7, 10.5, TZ + 0.45, TZ + 0.6, "cushion", "Terraces")
    r.span("Sofa_L2", -7.6, -6.6, 6.6, 9.6, TZ, TZ + 0.45, "graphite", "Terraces")
    r.span("Sofa_L2_Cushion", -7.5, -6.7, 6.7, 9.6, TZ + 0.45, TZ + 0.6, "cushion", "Terraces")
    r.span("FireTable", -5.2, -3.0, 7.6, 8.8, TZ, TZ + 0.4, "concrete", "Terraces")
    r.span("FireTable_Flame", -4.9, -3.3, 8.0, 8.4, TZ + 0.4, TZ + 0.48, "fire", "Terraces")
    r.light("Fire_Glow", (-4.1, 8.2, TZ + 0.9), "#ff9a4a", 160, 0.6)
    for sx in (-8.0, -0.4):
        for sy in (7.6, 11.0):
            r.span(f"Pergola_Post{sx}_{sy}", sx, sx + 0.14, sy - 0.14, sy, TZ, TZ + 2.9, "metal", "Terraces")
    for k in range(13):
        y = 7.6 + k * 0.28
        r.span(f"Pergola_Slat{k}", -8.0, -0.26, y, y + 0.1, TZ + 2.9, TZ + 3.05, "wood", "Terraces")
    # glass balustrade on the terrace edge, steps down to the private garden
    r.glass_rail("T_Rail_N_W", -8.0, -1.2, 11.18, 11.18, TZ)
    r.glass_rail("T_Rail_N_E", 1.2, 13.2, 11.18, 11.18, TZ)
    r.glass_rail("T_Rail_E", 13.18, 13.18, 5.0, 11.2, TZ)
    for k in range(2):
        r.span(f"T_Step{k}", -1.2, 1.2, 11.2 + k * 0.4, 11.6 + k * 0.4, G, TZ - (k + 1) * 0.1, "concrete", "Terraces")
    r.span("T_LED", -8.0, 13.2, 11.2, 11.26, G, TZ - 0.04, "led", "Terraces")       # warm line on the terrace edge
    # covered dining + outdoor kitchen under the east cantilever
    r.span("Dining_Deck", 8.0, 13.2, -3.5, 5.0, G, TZ, "deck", "Terraces")
    r.span("Dining_Table", 9.4, 11.6, -0.6, 2.6, TZ, TZ + 0.75, "wood", "Terraces")
    for k in range(4):
        for sx in (9.1, 11.9):
            y = -0.2 + k * 0.85
            r.span(f"Dining_Chair{k}_{sx}", sx - 0.22, sx + 0.22, y - 0.22, y + 0.22, TZ, TZ + 0.45, "graphite", "Terraces")
    r.span("Kitchen_Counter", 12.5, 13.1, -3.2, 2.4, TZ, TZ + 0.92, "graphite", "Terraces")
    r.span("Kitchen_Top", 12.45, 13.15, -3.25, 2.45, TZ + 0.92, TZ + 0.97, "concrete", "Terraces")
    r.light("Dining_Light", (10.5, 1.0, Z1 - 0.6), "#ffc27a", 160, 0.8)

    # ---------------------------------------------------------------- landscape: green garden, front pool, lighting
    r.span("Reflect_Pool", 5.0, 12.5, -10.2, -8.0, G, G + 0.12, "concrete", "Landscape")
    r.span("Reflect_Water", 5.2, 12.3, -10.0, -8.2, G + 0.12, G + 0.15, "pool", "Landscape")
    for k in range(4):
        r.span(f"Stepstone{k}", 2.2 + k * 0.9, 2.9 + k * 0.9, -9.6, -8.6, G, G + 0.05, "concrete", "Landscape")
    trees = [((3.9, -12.3), "round", 1.0), ((10.5, -12.6), "columnar", 1.0), ((13.0, -6.0), "columnar", 0.9),
             ((-12.0, 13.0), "columnar", 1.0), ((-7.0, 13.2), "round", 0.9), ((8.5, 13.1), "round", 0.9),
             ((12.6, 12.8), "columnar", 1.0), ((-13.0, 9.5), "round", 0.85)]
    for i, (p, shape, size) in enumerate(trees):
        r.tree(f"Tree{i}", (p[0], p[1], G), shape, size)
    shrubs = [(2.5, -13.0), (2.4, -11.2), (6.0, -11.6), (4.2, -6.9), (6.6, -12.9), (13.2, -9.5),
              (-13.2, 6.0), (-13.2, 3.5), (5.0, 12.6), (-3.5, 12.9), (13.3, 8.0)]
    for i, p in enumerate(shrubs):
        r.shrub(f"Shrub{i}", (p[0], p[1], G), 0.5)
    r.uplights("Uplight_S", [(-7.0, -5.6), (-4.0, -5.6), (6.0, -5.6), (7.6, -5.6), (-12.5, -6.6), (-8.4, -6.6)])
    r.uplights("Uplight_E", [(13.6, -2.0), (13.6, 2.0)])
    r.uplights("Uplight_W", [(-13.6, -4.0), (-13.6, -1.0), (-13.6, 2.0)])
    r.uplights("Uplight_N", [(-6.0, 11.7), (6.0, 11.7), (11.0, 11.7)])
    for i, x in enumerate((-13.6, -2.4, 2.4, 13.6)):       # garden bollards along the front
        r.cyl(f"Front_Bollard{i}", 0.08, 0.08, 0.6, 8, (x, -13.4, G), "uplight", "Landscape")


def build_sign(r):
    """Illuminated founder monolith on the Cross Street frontage, facing south."""
    hy = PLOT_HALF[1]
    sx, sy = -5.4, -hy + 0.55          # in the bay of the front boundary wall, by the entry walk
    r.span("Sign_Plinth", sx - 2.0, sx + 2.0, sy - 0.45, sy + 0.45, G, G + 0.25, "concrete", "Sign")
    r.span("Sign_Monolith", sx - 1.8, sx + 1.8, sy - 0.2, sy + 0.2, G + 0.25, G + 2.15, "concrete", "Sign")
    r.span("Sign_Panel", sx - 1.6, sx + 1.6, sy - 0.24, sy - 0.2, G + 0.45, G + 1.95, "graphite", "Sign")
    r.span("Sign_Bar", sx - 1.2, sx + 1.2, sy - 0.27, sy - 0.24, G + 1.5, G + 1.53, "sign_gold", "Sign")
    r.span("Sign_Base_LED", sx - 1.8, sx + 1.8, sy - 0.47, sy - 0.43, G + 0.02, G + 0.05, "led", "Sign")
    lines = [(RESIDENT["sign_lines"][0], 0.19, G + 1.7), (RESIDENT["sign_lines"][1], 0.3, G + 1.1), (RESIDENT["sign_lines"][2], 0.17, G + 0.72)]
    for i, (txt, size, z) in enumerate(lines):
        cu = bpy.data.curves.new(f"{PREFIX}_SignText{i}", "FONT")
        cu.body = txt
        cu.size = size
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.extrude = 0.012
        cu.space_character = 1.15 if i != 1 else 1.05
        cu.materials.append(r.m["sign_gold"])
        ob = bpy.data.objects.new(cu.name, cu)
        r.sub["Sign"].objects.link(ob)
        ob.parent = r.root
        ob.location = (sx, sy - 0.26, z)
        ob.rotation_euler = (math.radians(90), 0, 0)      # text faces -Y (Cross Street)
    r.light("Sign_Wash", (sx, sy - 1.4, G + 0.3), "#ffcf8a", 60, 0.3)
    return Vector((sx, sy - 0.26, G + 1.1))


# --------------------------------------------------------------------------- cameras

CAMERAS = {
    # name: (local location, local target, lens)
    "Resident001_Front": ((-4.0, -24.0, 8.0), (0.0, -1.0, 2.4), 18),
    "Resident001_Waterfront": ((4.0, 26.0, 7.5), (2.0, 3.0, 2.4), 18),
    "Resident001_Left": ((-24.0, 6.0, 8.0), (-2.0, 1.0, 2.4), 18),      # west facade
    "Resident001_Right": ((24.0, -2.0, 10.0), (4.0, 0.5, 2.4), 18),     # east facade
    "Resident001_Aerial": ((-15.0, -20.0, 25.0), (1.0, 1.5, 0.0), 22),
    "Resident001_Sign": ((-5.4, -20.5, 1.5), (-5.4, -14.5, 1.25), 40),
}


CITY_OVERVIEW = ((-2.0, -50.0, 46.0), (44.0, 18.0, 0.0))   # world location, world target


def add_cameras(r):
    cams = {}
    for name, (loc, tgt, lens) in CAMERAS.items():
        for old in (name, f"{name}_Target"):
            ob = bpy.data.objects.get(old)
            if ob:
                bpy.data.objects.remove(ob, do_unlink=True)
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = 36
        cd.clip_end = 3000
        cam = bpy.data.objects.new(name, cd)
        r.sub["Cameras"].objects.link(cam)
        cam.parent = r.root
        cam.location = loc
        t = bpy.data.objects.new(f"{name}_Target", None)
        t.empty_display_size = 0.4
        r.sub["Cameras"].objects.link(t)
        t.parent = r.root
        t.location = tgt
        con = cam.constraints.new("TRACK_TO")
        con.target = t
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        cams[name] = cam
    # 360 degree orbit (prepared, not rendered): camera on a rotating pivot, 480 frames = 20 s @ 24 fps
    pivot = bpy.data.objects.new("Resident001_OrbitPivot", None)
    r.sub["Cameras"].objects.link(pivot)
    pivot.parent = r.root
    pivot.location = (1.0, 1.0, 0.0)
    cd = bpy.data.cameras.new("Resident001_Orbit")
    cd.lens = 20
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36
    cam = bpy.data.objects.new("Resident001_Orbit", cd)
    r.sub["Cameras"].objects.link(cam)
    cam.parent = pivot
    cam.location = (0.0, -32.0, 9.0)
    t = bpy.data.objects.new("Resident001_Orbit_Target", None)
    r.sub["Cameras"].objects.link(t)
    t.parent = r.root
    t.location = (1.0, 1.0, 3.2)
    con = cam.constraints.new("TRACK_TO")
    con.target = t
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    pivot.rotation_euler.z = 0.0
    pivot.keyframe_insert("rotation_euler", index=2, frame=1)
    pivot.rotation_euler.z = 2 * math.pi
    pivot.keyframe_insert("rotation_euler", index=2, frame=481)
    for fc in pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    pivot.rotation_euler.z = 0.0
    cams["Resident001_Orbit"] = cam
    # city overview (world space, not parented): where the estate sits in the district
    old = bpy.data.objects.get("Resident001_CityOverview")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cd = bpy.data.cameras.new("Resident001_CityOverview")
    cd.lens = 24
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36
    cd.clip_end = 3000
    ov = bpy.data.objects.new("Resident001_CityOverview", cd)
    r.sub["Cameras"].objects.link(ov)
    ov.location = CITY_OVERVIEW[0]
    ov.rotation_euler = (Vector(CITY_OVERVIEW[1]) - Vector(CITY_OVERVIEW[0])).to_track_quat("-Z", "Y").to_euler()
    cams["Resident001_CityOverview"] = ov
    return cams


# --------------------------------------------------------------------------- city integration & checks

SKIP_BIG = ("Ground", "Lake", "FarShore", "Sun_Disc")


def world_bbox(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))


def overlaps(a, b, tol=0.02):
    return all(a[0][i] < b[1][i] - tol and b[0][i] < a[1][i] - tol for i in range(3))


def plot_bbox(margin=0.0):
    hx, hy = PLOT_HALF
    return (Vector((PLOT_CENTER.x - hx - margin, PLOT_CENTER.y - hy - margin, 0.0)),
            Vector((PLOT_CENTER.x + hx + margin, PLOT_CENTER.y + hy + margin, 20.0)))


def clear_plot():
    """Remove city objects standing on the founder plot (only free-standing meadow trees live there)."""
    pb = plot_bbox(0.0)
    removed, conflicts = set(), []
    for ob in list(bpy.data.objects):
        if ob.type != "MESH" or ob.name.startswith(PREFIX) or ob.name.startswith(SKIP_BIG):
            continue
        bb = world_bbox(ob)
        if (bb[1] - bb[0]).x > 150:
            continue
        if overlaps(bb, pb, tol=0.0):
            if ob.name.startswith("T_"):
                removed.add(ob.name.rsplit("_", 1)[0])
            else:
                conflicts.append(ob.name)
    for ob in list(bpy.data.objects):
        if ob.type == "MESH" and ob.name.rsplit("_", 1)[0] in removed:
            bpy.data.objects.remove(ob, do_unlink=True)
    return sorted(removed), conflicts


def residence_objects():
    col = bpy.data.collections[COLLECTION]
    return [o for o in col.all_objects if o.type in ("MESH", "FONT")]


def validate(cams, sign_world):
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    res = residence_objects()
    res_set = {o.name for o in res}
    rep = {}
    # 1) no intersections with city geometry
    city = [o for o in bpy.data.objects if o.type == "MESH" and o.name not in res_set and not o.name.startswith(SKIP_BIG)]
    city_bb = [(o.name, world_bbox(o)) for o in city]
    hits = []
    for o in res:
        bb = world_bbox(o)
        for n, cb in city_bb:
            if overlaps(bb, cb):
                hits.append(f"{o.name} x {n}")
    rep["intersections_with_city"] = hits
    # 2) promenade stays public: nothing of the estate reaches y >= 36.2
    max_y = max(world_bbox(o)[1].y for o in res)
    rep["estate_max_y"] = round(max_y, 2)
    rep["promenade_clear"] = max_y < PROMENADE_Y
    # 3) estate footprint and size vs. neighbours
    house = [o for o in res if o.users_collection[0].name.endswith("_House")]
    lo = Vector((min(world_bbox(o)[0][i] for o in house) for i in range(3)))
    hi = Vector((max(world_bbox(o)[1][i] for o in house) for i in range(3)))
    rep["house_bbox"] = [[round(v, 1) for v in lo], [round(v, 1) for v in hi]]
    neigh = []
    for root in [o for o in bpy.data.objects if o.name.startswith("House_") and o.parent is None and o.type == "EMPTY"]:
        kids = [k for k in root.children_recursive if k.type == "MESH" and "lawn" not in k.name and "hedge" not in k.name]
        if not kids:
            continue
        a = Vector((min(world_bbox(k)[0][i] for k in kids) for i in range(3)))
        b = Vector((max(world_bbox(k)[1][i] for k in kids) for i in range(3)))
        neigh.append(((b - a).x * (b - a).y, (b - a).z))
    if neigh:
        rep["neighbour_avg_footprint_m2"] = round(sum(n[0] for n in neigh) / len(neigh), 1)
        rep["neighbour_max_height_m"] = round(max(n[1] for n in neigh), 1)
    rep["house_footprint_m2"] = round((hi - lo).x * (hi - lo).y, 1)
    rep["house_height_m"] = round(hi.z - lo.z, 1)
    # 4) camera framing: share of frame covered by the estate, no near occluders from the city
    from bpy_extras.object_utils import world_to_camera_view  # noqa: F401
    cam_rep = {}
    for name, cam in cams.items():
        if name in ("Resident001_Orbit", "Resident001_CityOverview"):
            continue
        mw = cam.matrix_world
        o = mw.translation.copy()
        tr, br, bl, tl = cam.data.view_frame(scene=scene)
        n = own = near = 0
        for iy in range(24):
            for ix in range(14):
                d = (mw.to_3x3() @ tl.lerp(bl, (iy + 0.5) / 24).lerp(tr.lerp(br, (iy + 0.5) / 24), (ix + 0.5) / 14)).normalized()
                hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, o, d, distance=500)
                n += 1
                if hit and ob.name in res_set:
                    own += 1
                elif hit and (loc - o).length < 8.0 and _n.z < 0.7:
                    near += 1
        cam_rep[name] = {"estate_share": round(own / n, 2), "near_city_occluder_share": round(near / n, 3)}
    rep["cameras"] = cam_rep
    # 5) sign readable from its close-up camera (line of sight to the text centre)
    sc = cams["Resident001_Sign"].matrix_world.translation
    d = sign_world - sc
    hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, sc, d.normalized(), distance=d.length + 0.5)
    rep["sign_line_of_sight"] = bool(hit and ob.name.startswith(f"{PREFIX}_Sign"))
    # 6) visible from the public waterfront: rays from the boardwalk / pier lookout to the house
    seen = 0
    spots = [Vector((x, 40.5, 1.7)) for x in (45, 55, 65, 75)] + [Vector((-9, 67, 1.6))]
    for p in spots:
        tgt = PLOT_CENTER + Vector((2, 4, 4.5))
        d = tgt - p
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, p, d.normalized(), distance=d.length + 1)
        seen += bool(hit and ob.name in res_set)
    rep["visible_from_waterfront_spots"] = f"{seen}/{len(spots)}"
    # 7) city cameras still present, trees still green
    rep["city_cameras"] = {n: bool(bpy.data.objects.get(n)) for n in ("Cam_Cinematic", "Cam_Reels")}
    rep["cinematic_keyframes"] = len(bpy.data.objects["Cam_Cinematic"].animation_data.action.fcurves[0].keyframe_points) if bpy.data.objects.get("Cam_Cinematic") else 0
    crowns = [o for o in bpy.data.objects if "_crown" in o.name or "_lobe" in o.name]
    rep["tree_crowns"] = len(crowns)
    rep["non_green_crowns"] = sorted({o.active_material.name for o in crowns if not o.active_material.name.startswith(("leaf_", "shrub"))})
    return rep


# --------------------------------------------------------------------------- main

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--city", default=os.path.join(HERE, "..", "..", "episode-001", "scenes", "noc_ep001_district.blend"))
    p.add_argument("--standalone", action="store_true")
    p.add_argument("--save", default="")
    p.add_argument("--renders", default="", help="directory for the light check renders")
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--report", default="")
    return p.parse_known_args(argv)[0]


def build(standalone):
    if standalone:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bd.MATS.clear()
        bd.COLLS.clear()
        import random
        random.seed(1)
        bd.build_materials()
        bd.build_world()
        bd.build_lights()
        bd.build_ground_and_water()      # same ground, lake and public waterfront as the city, same coordinates
        bd.setup_render(SimpleNamespace(samples=96, preview=False))
        removed, conflicts = [], []
    else:
        bd.MATS.clear()
        bd.MATS.update({m.name: m for m in bpy.data.materials})
        bd.COLLS.clear()
        bd.COLLS.update({c.name: c for c in bpy.data.collections})
        removed, conflicts = clear_plot()
    mats = build_materials()
    r = Residence(mats)
    build_estate(r)
    sign_local = build_sign(r)
    cams = add_cameras(r)
    r.root.location = PLOT_CENTER          # place the whole module on plot NOC-001
    bpy.context.view_layer.update()
    sign_world = r.root.matrix_world @ sign_local
    return r, cams, sign_world, removed, conflicts


def render_checks(cams, out_dir, samples):
    s = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    s.render.engine = "CYCLES"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.render.resolution_percentage = 50
    s.render.image_settings.file_format = "PNG"
    s.frame_set(1)
    keep_cam = s.camera
    for name in list(CAMERAS) + ["Resident001_CityOverview"]:
        s.camera = bpy.data.objects[name]
        s.render.filepath = os.path.join(os.path.abspath(out_dir), f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("[RES001] rendered", name)
    s.camera = keep_cam


def main():
    args = parse_args()
    if not args.standalone:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.city))
    r, cams, sign_world, removed, conflicts = build(args.standalone)
    print(f"[RES001] built {len(residence_objects())} objects in {COLLECTION}; plot centre {tuple(PLOT_CENTER)}")
    if not args.standalone:
        print(f"[RES001] cleared from plot: {len(removed)} meadow trees {removed}; other conflicts: {conflicts}")
        rep = validate(cams, sign_world)
        rep["trees_removed_from_plot"] = removed
        rep["plot_conflicts"] = conflicts
        for k, v in rep.items():
            print(f"[RES001] {k}: {v}")
        if args.report:
            import json
            with open(args.report, "w") as fh:
                json.dump(rep, fh, indent=1, ensure_ascii=False)
    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
        s = bpy.context.scene
        if args.standalone:
            s.camera = cams["Resident001_Waterfront"]
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save), compress=True)
        print("[RES001] saved", os.path.abspath(args.save))
    if args.renders:
        render_checks(cams, args.renders, args.samples)


if __name__ == "__main__":
    main()
