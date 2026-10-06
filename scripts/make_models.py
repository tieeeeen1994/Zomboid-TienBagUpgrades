"""Builds the dropped (world) models of the upgrade items.

    python3 scripts/make_models.py            # mesh + textures into the mod
    python3 scripts/make_models.py --preview  # also renders tmp/models_preview.png

Needs Pillow and a local Project Zomboid install (the vanilla meshes are used as templates). Writes:
  Contents/mods/TienBagUpgrades/42/media/models_X/WorldItems/TienBagUpgrades_Pouch.fbx
  Contents/mods/TienBagUpgrades/42/media/models_X/WorldItems/TienBagUpgrades_Strap.fbx
  Contents/mods/TienBagUpgrades/42/media/textures/WorldItems/TienBagUpgrades_Pouch<Material>.png   128x128
  Contents/mods/TienBagUpgrades/42/media/textures/WorldItems/TienBagUpgrades_Strap<Material>.png   128x128

Both meshes are built here vertex by vertex:
  Bag upgrades:    a padded pouch with a flap and a closing tab, lying on its back.
  Straps upgrades: a padded shoulder strap lying in a gentle S, webbing running out of both ends of the pad, a
                   ladder-lock buckle on one end and a ring on the other.
Each is written into a copy of vanilla's M_FannyPackFront_Ground.fbx with only the geometry replaced, so it keeps
that file's header, axis settings, model transforms and material: the game loads it exactly like the fanny pack.
Coordinates are in that file's raw frame (Z up, ground at z = 0, the fanny pack is 18 x 16 x 6 units).
"""

import io
import math
import os
import random
import re
import struct
import sys

from PIL import Image, ImageDraw, ImageEnhance

import fbx_bin
import pz_model

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MOD = os.path.join(REPO, "Contents", "mods", "TienBagUpgrades", "42", "media")
POUCH_OUT = os.path.join(MOD, "models_X", "WorldItems", "TienBagUpgrades_Pouch.fbx")
STRAP_OUT = os.path.join(MOD, "models_X", "WorldItems", "TienBagUpgrades_Strap.fbx")
TEX_OUT = os.path.join(MOD, "textures", "WorldItems")
ICON_OUT = os.path.join(MOD, "textures")
PZ_MEDIA = os.path.expanduser(
    "~/Library/Application Support/Steam/steamapps/common/ProjectZomboid/"
    "Project Zomboid.app/Contents/Java/media"
)
TEMPLATE = os.path.join(PZ_MEDIA, "models_X", "WorldItems", "Clothing", "M_FannyPackFront_Ground.fbx")

# Colours picked to match Dynamic Backpack Upgrades' item icons.
MATERIALS = {
    "Cloth": dict(base=(214, 206, 188), dark=(170, 160, 140), light=(236, 230, 216), stitch=(130, 118, 98),
                  webbing=(168, 156, 132), buckle="metal"),
    "Jean": dict(base=(72, 102, 150), dark=(50, 72, 112), light=(100, 132, 180), stitch=(214, 150, 72),
                 webbing=(46, 58, 90), buckle="metal"),
    "Leather": dict(base=(160, 86, 44), dark=(116, 58, 28), light=(190, 116, 66), stitch=(228, 196, 146),
                    webbing=(104, 54, 26), buckle="brass"),
    "Military": dict(base=(98, 108, 68), dark=(70, 78, 46), light=(124, 134, 90), stitch=(58, 64, 38),
                     webbing=(62, 70, 40), buckle="plastic"),
}

TEX = 128  # pouch texture size

# Pouch texture layout, in pixels (x0, y0, x1, y1).
R_FRONT = (0, 0, 64, 64)        # top face of the body (the pouch's front, facing up)
R_FLAP = (64, 0, 128, 40)       # flap, top side
R_FLAP_EDGE = (64, 40, 128, 48)  # flap, thickness strip
R_TAB = (64, 48, 96, 64)        # closing tab
R_BACK = (96, 48, 128, 64)      # bottom face
R_SIDES = (0, 64, 128, 96)      # body sides, unrolled
R_BEVEL = (0, 96, 128, 112)     # rounded edges top and bottom, unrolled

# Strap texture layout: the strip runs along texture x from the buckle end (x = 0) to the ring end (x = 128).
S_TOP = (0, 0, 128, 48)         # top surface, across the width along y
S_SIDE = (0, 48, 128, 56)       # both long sides
S_BOTTOM = (0, 56, 128, 72)     # underside
S_CAP = (0, 72, 32, 80)         # the two end faces
S_METAL = (0, 96, 64, 128)      # buckle and ring: top half lit, bottom half shaded
PAD_FROM, PAD_TO = 0.22, 0.78   # the padded part, as a share of the strip's length


# --------------------------------------------------------------------------------------------------
# Mesh
# --------------------------------------------------------------------------------------------------

class Mesh:
    def __init__(self):
        self.faces = []  # (group, [(pos, uv)])

    def face(self, group, corners):
        self.faces.append((group, corners))


def uv_in(rect, fx, fy):
    """Texture coordinates (FBX convention, v up) of a point at fractions fx, fy of a pixel rect."""
    x0, y0, x1, y1 = rect
    x = x0 + (x1 - x0) * fx
    y = y0 + (y1 - y0) * fy
    return (x / TEX, 1 - y / TEX)


def rounded_rect(w, l, r, segs=3):
    """Footprint points, counter-clockwise from the front right, of a w x l rectangle with round corners."""
    pts = []
    corners = [(w / 2 - r, -l / 2 + r, -90), (w / 2 - r, l / 2 - r, 0), (-w / 2 + r, l / 2 - r, 90),
               (-w / 2 + r, -l / 2 + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(segs + 1):
            a = math.radians(a0 + 90 * i / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def scale_pts(pts, k):
    return [(x * k, y * k) for x, y in pts]


def perimeter_params(pts):
    d = [0.0]
    for i in range(1, len(pts) + 1):
        a, b = pts[i - 1], pts[i % len(pts)]
        d.append(d[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return [x / d[-1] for x in d]


def ring_band(mesh, group, lower, upper, rect):
    """Quads between two closed rings of 3D points with the same count, unrolled into rect."""
    t = perimeter_params([(p[0], p[1]) for p in lower])
    n = len(lower)
    for i in range(n):
        j = (i + 1) % n
        u0, u1 = t[i], t[i + 1]
        mesh.face(group, [(lower[i], uv_in(rect, u0, 1)), (lower[j], uv_in(rect, u1, 1)),
                          (upper[j], uv_in(rect, u1, 0)), (upper[i], uv_in(rect, u0, 0))])


def planar_fan(mesh, group, ring, centre, rect, bounds, up):
    """A fan from a centre point to a ring, mapped by x / y into rect (bounds = x0, y0, x1, y1 in the model)."""
    bx0, by0, bx1, by1 = bounds

    def uv(p):
        fx = (p[0] - bx0) / (bx1 - bx0)
        fy = (by1 - p[1]) / (by1 - by0)
        return uv_in(rect, fx, fy)

    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        tri = [(centre, uv(centre)), (ring[i], uv(ring[i])), (ring[j], uv(ring[j]))]
        mesh.face(group, tri if up else tri[::-1])


def build_pouch():
    """The bag upgrade: a padded pouch lying on its back, flap closed, a tab down the front."""
    mesh = Mesh()
    W, L, H = 13.0, 15.0, 4.2
    foot = rounded_rect(W, L, 2.0)
    bounds = (-W / 2, -L / 2, W / 2, L / 2)

    bottom_in = [(x, y, 0.0) for x, y in scale_pts(foot, 0.9)]
    low = [(x, y, 0.7) for x, y in foot]
    high = [(x, y, H) for x, y in foot]
    top_in = [(x, y, H + 0.7) for x, y in scale_pts(foot, 0.88)]

    planar_fan(mesh, 1, bottom_in, (0, 0, 0.0), R_BACK, bounds, up=False)
    ring_band(mesh, 2, bottom_in, low, (R_BEVEL[0], R_BEVEL[1] + 8, R_BEVEL[2], R_BEVEL[3]))
    ring_band(mesh, 2, low, high, R_SIDES)
    ring_band(mesh, 2, high, top_in, (R_BEVEL[0], R_BEVEL[1], R_BEVEL[2], R_BEVEL[1] + 8))
    planar_fan(mesh, 3, top_in, (0, 0, H + 1.0), R_FRONT, bounds, up=True)

    # Flap: a draped sheet over the back half, wrapping down over the sides and the back edge.
    fy0, fy1 = -1.2, L / 2 + 0.35
    fx = W / 2 + 0.3
    nx, ny = 8, 6

    def flap_z(x, y):
        sx = min(1.0, (fx - abs(x)) / 1.6)
        sy = min(1.0, (fy1 - y) / 1.6)
        return H + 0.35 + 0.95 * math.sin(max(0.0, sx) * math.pi / 2) * math.sin(max(0.0, sy) * math.pi / 2)

    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = -fx + 2 * fx * i / nx
            y = fy0 + (fy1 - fy0) * j / ny
            if j == 0 and i in (0, nx):           # round the flap's front corners
                x *= 0.8
                y += 0.4
            row.append((x, y, flap_z(x, y) + (0.15 if j == 0 else 0.0)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
            uv = lambda p: uv_in(R_FLAP, (p[0] + fx) / (2 * fx), (fy1 - p[1]) / (fy1 - fy0))
            mesh.face(4, [(a, uv(a)), (b, uv(b)), (c, uv(c)), (d, uv(d))])
    # Flap thickness along its front edge and sides.
    edge = [grid[ny][0]] + [grid[j][0] for j in range(ny - 1, -1, -1)] + grid[0][1:] + \
           [grid[j][nx] for j in range(1, ny + 1)]
    lower = [(x, y, z - 0.45) for x, y, z in edge]
    t = perimeter_params([(p[0], p[1]) for p in edge] + [(edge[0][0], edge[0][1])])
    for i in range(len(edge) - 1):
        a, b = edge[i], edge[i + 1]
        mesh.face(5, [(lower[i], uv_in(R_FLAP_EDGE, t[i], 1)), (lower[i + 1], uv_in(R_FLAP_EDGE, t[i + 1], 1)),
                      (b, uv_in(R_FLAP_EDGE, t[i + 1], 0)), (a, uv_in(R_FLAP_EDGE, t[i], 0))])

    # Closing tab: a small padded box from the flap down onto the front.
    tx, ty0, ty1 = 1.2, fy0 - 2.2, fy0 + 1.0
    z0, z1 = H + 0.55, H + 1.75

    def box(x0, x1, y0, y1, z0, z1, rect, group):
        p = lambda x, y, z: (x, y, z)
        top = [p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)]
        sides = [
            [p(x0, y0, z0), p(x1, y0, z0), p(x1, y0, z1), p(x0, y0, z1)],
            [p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), p(x1, y0, z1)],
            [p(x1, y1, z0), p(x0, y1, z0), p(x0, y1, z1), p(x1, y1, z1)],
            [p(x0, y1, z0), p(x0, y0, z0), p(x0, y0, z1), p(x0, y1, z1)],
        ]
        top_rect = (rect[0], rect[1], rect[0] + (rect[2] - rect[0]) // 2, rect[3])
        side_rect = (rect[0] + (rect[2] - rect[0]) // 2, rect[1], rect[2], rect[3])
        mesh.face(group, [(q, uv_in(top_rect, (q[0] - x0) / (x1 - x0), (y1 - q[1]) / (y1 - y0))) for q in top])
        for quad in sides:
            mesh.face(group, [(quad[0], uv_in(side_rect, 0, 1)), (quad[1], uv_in(side_rect, 1, 1)),
                              (quad[2], uv_in(side_rect, 1, 0)), (quad[3], uv_in(side_rect, 0, 0))])

    box(-tx, tx, ty0, ty1, z0, z1, R_TAB, 6)
    return mesh


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def build_strap(coiled=False):
    """The straps upgrade: a padded shoulder strap lying in a gentle S, webbing out of both ends of the pad, a
    ladder-lock buckle on the first end and a rectangular ring on the other."""
    mesh = Mesh()
    length, stations, across = 30.0, 48, 6

    def centre(s):
        if coiled:
            # The icon's pose: the same strap curled into a C, so it fills a square icon.
            span = math.radians(230)
            radius = length / span
            a = math.radians(205) - span * s
            return (radius * math.cos(a), radius * math.sin(a))
        x = -length / 2 + length * s
        return (x, 2.2 * math.sin(math.pi * (s * 1.6 - 0.3)))

    # Arc length along the curve, to keep the texture even.
    samples = [centre(i / 400) for i in range(401)]
    dist = [0.0]
    for i in range(1, len(samples)):
        dist.append(dist[-1] + math.hypot(samples[i][0] - samples[i - 1][0], samples[i][1] - samples[i - 1][1]))

    def at(t):
        """Point and unit tangent at share t of the arc length."""
        target = t * dist[-1]
        i = max(1, min(len(dist) - 1, next((k for k, d in enumerate(dist) if d >= target), len(dist) - 1)))
        a, b = samples[i - 1], samples[i]
        span = dist[i] - dist[i - 1] or 1.0
        f = (target - dist[i - 1]) / span
        p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        tx, ty = b[0] - a[0], b[1] - a[1]
        n = math.hypot(tx, ty) or 1.0
        return p, (tx / n, ty / n)

    def size(t):
        pad = smoothstep(PAD_FROM - 0.05, PAD_FROM + 0.02, t) * (1 - smoothstep(PAD_TO - 0.02, PAD_TO + 0.05, t))
        return 2.6 + 2.8 * pad, 0.35 + 1.25 * pad   # width, thickness

    sections = []
    for i in range(stations + 1):
        t = i / stations
        (cx, cy), (tx, ty) = at(t)
        nx, ny = -ty, tx
        w, h = size(t)
        top = []
        for k in range(across + 1):
            u = -1 + 2 * k / across
            z = h * (0.3 + 0.7 * math.sqrt(max(0.0, 1 - u * u)))
            top.append((cx + nx * u * w / 2, cy + ny * u * w / 2, z))
        bottom = [(cx + nx * w / 2, cy + ny * w / 2, 0.0), (cx - nx * w / 2, cy - ny * w / 2, 0.0)]
        sections.append((t, top, bottom))

    for i in range(stations):
        t0, top0, bot0 = sections[i]
        t1, top1, bot1 = sections[i + 1]
        for k in range(across):
            f0, f1 = k / across, (k + 1) / across
            mesh.face(1, [(top0[k + 1], uv_in(S_TOP, t0, f1)), (top1[k + 1], uv_in(S_TOP, t1, f1)),
                          (top1[k], uv_in(S_TOP, t1, f0)), (top0[k], uv_in(S_TOP, t0, f0))])
        # long sides: right (u = +1) then left (u = -1)
        mesh.face(2, [(bot0[0], uv_in(S_SIDE, t0, 1)), (bot1[0], uv_in(S_SIDE, t1, 1)),
                      (top1[across], uv_in(S_SIDE, t1, 0)), (top0[across], uv_in(S_SIDE, t0, 0))])
        mesh.face(3, [(top0[0], uv_in(S_SIDE, t0, 0)), (top1[0], uv_in(S_SIDE, t1, 0)),
                      (bot1[1], uv_in(S_SIDE, t1, 1)), (bot0[1], uv_in(S_SIDE, t0, 1))])
        mesh.face(4, [(bot0[1], uv_in(S_BOTTOM, t0, 0)), (bot1[1], uv_in(S_BOTTOM, t1, 0)),
                      (bot1[0], uv_in(S_BOTTOM, t1, 1)), (bot0[0], uv_in(S_BOTTOM, t0, 1))])

    # The quads above were listed clockwise seen from outside; turn them round.
    mesh.faces = [(g, c[::-1]) for g, c in mesh.faces]

    # End caps.
    for t, top, bottom in (sections[0], sections[-1]):
        ring = [bottom[1]] + top + [bottom[0]]
        if t == 0:
            ring = ring[::-1]
        c = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring),
             sum(p[2] for p in ring) / len(ring))
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            mesh.face(5, [(c, uv_in(S_CAP, 0.5, 0.5)), (b, uv_in(S_CAP, 0.9, 0.2)), (a, uv_in(S_CAP, 0.1, 0.2))])

    # Hardware: frames of square bars, flat shaded (each face its own group).
    group = [100]

    def bar(p0, p1, half_w, z0, z1):
        """A square bar from p0 to p1 (ground plane points), half_w thick, from z0 to z1."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n * half_w, dx / n * half_w
        a0 = (p0[0] - nx, p0[1] - ny); b0 = (p0[0] + nx, p0[1] + ny)
        a1 = (p1[0] - nx, p1[1] - ny); b1 = (p1[0] + nx, p1[1] + ny)
        quads = [
            [(a0[0], a0[1], z1), (b0[0], b0[1], z1), (b1[0], b1[1], z1), (a1[0], a1[1], z1)],   # top
            [(b0[0], b0[1], z0), (b1[0], b1[1], z0), (b1[0], b1[1], z1), (b0[0], b0[1], z1)],
            [(a1[0], a1[1], z0), (a0[0], a0[1], z0), (a0[0], a0[1], z1), (a1[0], a1[1], z1)],
            [(a0[0], a0[1], z0), (b0[0], b0[1], z0), (b0[0], b0[1], z1), (a0[0], a0[1], z1)],
            [(b1[0], b1[1], z0), (a1[0], a1[1], z0), (a1[0], a1[1], z1), (b1[0], b1[1], z1)],
        ]
        centre_ = [sum(q[i] for quad in quads for q in quad) / 20 for i in range(3)]
        for qi, quad in enumerate(quads):
            # counter-clockwise seen from outside: the winding's normal points away from the bar's centre
            nx_ = ny_ = nz_ = 0.0
            for k in range(4):
                a, b = quad[k], quad[(k + 1) % 4]
                nx_ += (a[1] - b[1]) * (a[2] + b[2])
                ny_ += (a[2] - b[2]) * (a[0] + b[0])
                nz_ += (a[0] - b[0]) * (a[1] + b[1])
            fc = [sum(q[i] for q in quad) / 4 for i in range(3)]
            if (fc[0] - centre_[0]) * nx_ + (fc[1] - centre_[1]) * ny_ + (fc[2] - centre_[2]) * nz_ < 0:
                quad = quad[::-1]
            half = (0, 0, 1, 0.5) if qi == 0 else (0, 0.5, 1, 1)
            rect = (S_METAL[0] + (S_METAL[2] - S_METAL[0]) * half[0], S_METAL[1] + (S_METAL[3] - S_METAL[1]) * half[1],
                    S_METAL[0] + (S_METAL[2] - S_METAL[0]) * half[2], S_METAL[1] + (S_METAL[3] - S_METAL[1]) * half[3])
            corners = [(quad[0], uv_in(rect, 0.1, 0.9)), (quad[1], uv_in(rect, 0.9, 0.9)),
                       (quad[2], uv_in(rect, 0.9, 0.1)), (quad[3], uv_in(rect, 0.1, 0.1))]
            group[0] += 1
            mesh.face(group[0], corners)

    def frame(t, outward, along, across_w, thick, z1, middle):
        (cx, cy), (tx, ty) = at(t)
        tx, ty = tx * outward, ty * outward
        nx, ny = -ty, tx
        o = (cx + tx * 0.2, cy + ty * 0.2)           # inner edge sits just past the strap end
        def pt(a, b):
            return (o[0] + tx * a + nx * b, o[1] + ty * a + ny * b)
        half = across_w / 2
        bar(pt(0, -half), pt(0, half), thick / 2, 0.0, z1)
        bar(pt(along, -half), pt(along, half), thick / 2, 0.0, z1)
        bar(pt(0, -half), pt(along, -half), thick / 2, 0.0, z1)
        bar(pt(0, half), pt(along, half), thick / 2, 0.0, z1)
        if middle:
            bar(pt(along / 2, -half), pt(along / 2, half), thick / 2, 0.0, z1 * 0.9)

    frame(0.0, -1, 2.4, 3.6, 0.5, 0.55, middle=True)    # ladder-lock buckle
    frame(1.0, 1, 1.8, 3.4, 0.45, 0.5, middle=False)    # ring
    return mesh


def normals_for(mesh):
    """Smooth normals inside each group (summed face normals per shared position), flat across groups."""
    def face_normal(corners):
        nx = ny = nz = 0.0
        pts = [c[0] for c in corners]
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        return nx, ny, nz

    acc = {}
    fn = []
    for group, corners in mesh.faces:
        n = face_normal(corners)
        fn.append(n)
        for pos, _ in corners:
            key = (group, tuple(round(c, 4) for c in pos))
            s = acc.get(key, (0.0, 0.0, 0.0))
            acc[key] = (s[0] + n[0], s[1] + n[1], s[2] + n[2])
    out = []
    for group, corners in mesh.faces:
        per = []
        for pos, _ in corners:
            x, y, z = acc[(group, tuple(round(c, 4) for c in pos))]
            length = math.sqrt(x * x + y * y + z * z) or 1.0
            per.append((x / length, y / length, z / length))
        out.append(per)
    return out


def write_mesh(mesh, path, model_name):
    """The mesh into a copy of the vanilla fanny pack file, geometry replaced, everything else kept."""
    fbx = fbx_bin.read(TEMPLATE)
    geometry = fbx.find("Objects", "Geometry")
    normals = normals_for(mesh)

    index = {}
    vertices, polygon_index, uvs, uv_index, normal_list = [], [], [], [], []
    uv_lookup = {}
    for (group, corners), corner_normals in zip(mesh.faces, normals):
        for k, ((pos, uv), n) in enumerate(zip(corners, corner_normals)):
            key = tuple(round(c, 5) for c in pos)
            if key not in index:
                index[key] = len(vertices) // 3
                vertices.extend(pos)
            vi = index[key]
            polygon_index.append(~vi if k == len(corners) - 1 else vi)
            ukey = (round(uv[0], 6), round(uv[1], 6))
            if ukey not in uv_lookup:
                uv_lookup[ukey] = len(uvs) // 2
                uvs.extend(ukey)
            uv_index.append(uv_lookup[ukey])
            normal_list.extend(n)

    def node(name, props, children=(), sentinel=False):
        return [name, list(props), list(children), sentinel]

    keep = [c for c in geometry[2] if c[0] == "Properties70"]
    layer = node("Layer", [("I", 0)], [
        node("Version", [("I", 100)]),
        node("LayerElement", [], [node("Type", [("S", b"LayerElementNormal")]), node("TypedIndex", [("I", 0)])]),
        node("LayerElement", [], [node("Type", [("S", b"LayerElementMaterial")]), node("TypedIndex", [("I", 0)])]),
        node("LayerElement", [], [node("Type", [("S", b"LayerElementUV")]), node("TypedIndex", [("I", 0)])]),
    ])
    geometry[2] = keep + [
        node("Vertices", [("d", vertices)]),
        node("PolygonVertexIndex", [("i", polygon_index)]),
        node("GeometryVersion", [("I", 124)]),
        node("LayerElementNormal", [("I", 0)], [
            node("Version", [("I", 101)]),
            node("Name", [("S", b"")]),
            node("MappingInformationType", [("S", b"ByPolygonVertex")]),
            node("ReferenceInformationType", [("S", b"Direct")]),
            node("Normals", [("d", normal_list)]),
        ]),
        node("LayerElementUV", [("I", 0)], [
            node("Version", [("I", 101)]),
            node("Name", [("S", b"UVChannel_1")]),
            node("MappingInformationType", [("S", b"ByPolygonVertex")]),
            node("ReferenceInformationType", [("S", b"IndexToDirect")]),
            node("UV", [("d", uvs)]),
            node("UVIndex", [("i", uv_index)]),
        ]),
        node("LayerElementMaterial", [("I", 0)], [
            node("Version", [("I", 101)]),
            node("Name", [("S", b"")]),
            node("MappingInformationType", [("S", b"AllSame")]),
            node("ReferenceInformationType", [("S", b"IndexToDirect")]),
            node("Materials", [("i", [0])]),
        ]),
        layer,
    ]
    # The model node keeps the vanilla name; rename it for clarity (the game looks up meshes by file).
    model = fbx.find("Objects", "Model")
    kind, name = model[1][1]
    model[1][1] = (kind, model_name.encode() + name[name.index(b"\x00\x01"):])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fbx_bin.write(fbx, path)
    return len(vertices) // 3, sum(len(c) - 2 for _, c in mesh.faces)


# --------------------------------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------------------------------

def clamp(c):
    return max(0, min(255, int(round(c))))


def tone(colour, k):
    return tuple(clamp(c * k) for c in colour)


def fill_material(img, rect, mat, rng, name):
    """Base colour with the material's surface: canvas weave, denim twill, leather grain, nylon weave."""
    c = MATERIALS[mat]
    px = img.load()
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            k = 1.0 + rng.uniform(-0.05, 0.05)
            if mat == "Jean":
                k += 0.07 if (x + y) % 3 == 0 else -0.02
            elif mat == "Cloth":
                k += 0.04 if (x % 2) ^ (y % 2) else -0.02
            elif mat == "Leather":
                k += rng.uniform(-0.06, 0.06) + 0.05 * math.sin(x * 0.7 + y * 0.3) * math.sin(y * 0.9)
            elif mat == "Military":
                k += 0.05 if y % 2 == 0 else -0.03
            px[x, y] = tone(c["base"], k) + (255,)


def stitch_rect(img, rect, colour, inset=2, sides="tlbr"):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect[0] + inset, rect[1] + inset, rect[2] - 1 - inset, rect[3] - 1 - inset
    def dashes(points):
        for i, p in enumerate(points):
            if i % 3 < 2:
                d.point(p, fill=colour)
    if "t" in sides:
        dashes([(x, y0) for x in range(x0, x1 + 1)])
    if "b" in sides:
        dashes([(x, y1) for x in range(x0, x1 + 1)])
    if "l" in sides:
        dashes([(x0, y) for y in range(y0, y1 + 1)])
    if "r" in sides:
        dashes([(x1, y) for y in range(y0, y1 + 1)])


def shade_edges(img, rect, colour, width=1):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect[0], rect[1], rect[2] - 1, rect[3] - 1
    for i in range(width):
        d.rectangle([x0 + i, y0 + i, x1 - i, y1 - i], outline=colour)


def pouch_texture(mat):
    c = MATERIALS[mat]
    rng = random.Random("pouch" + mat)
    img = Image.new("RGBA", (TEX, TEX), c["dark"] + (255,))
    for name, rect in (("front", R_FRONT), ("flap", R_FLAP), ("edge", R_FLAP_EDGE), ("tab", R_TAB),
                       ("back", R_BACK), ("sides", R_SIDES), ("bevel", R_BEVEL)):
        fill_material(img, rect, mat, rng, name)
    d = ImageDraw.Draw(img)

    # Front: webbing rows for military, a stitched border for the others; the flap covers its back half
    # (texture y 0..~35 of the front rect is under the flap).
    fx0, fy0, fx1, fy1 = R_FRONT
    if mat == "Military":
        for y in (fy0 + 38, fy0 + 47, fy0 + 56):
            d.rectangle([fx0 + 4, y, fx1 - 5, y + 4], fill=c["dark"])
            d.line([(fx0 + 4, y), (fx1 - 5, y)], fill=c["light"])
            for x in range(fx0 + 12, fx1 - 5, 12):
                d.line([(x, y), (x, y + 4)], fill=c["stitch"])
    stitch_rect(img, R_FRONT, c["stitch"], inset=3)

    # Flap: lighter, stitched border, a darker fold line along its back edge.
    x0, y0, x1, y1 = R_FLAP
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = img.getpixel((x, y))
            img.putpixel((x, y), tone((r, g, b), 1.08) + (255,))
    stitch_rect(img, R_FLAP, c["stitch"], inset=3, sides="tlr")
    d.line([(x0, y0), (x1 - 1, y0)], fill=c["dark"])
    d.line([(x0, y0 + 1), (x1 - 1, y0 + 1)], fill=c["dark"])

    # Flap edge: darker, with the stitch line along it.
    ex0, ey0, ex1, ey1 = R_FLAP_EDGE
    d.rectangle([ex0, ey0, ex1 - 1, ey1 - 1], fill=c["dark"])
    for x in range(ex0, ex1, 3):
        d.point((x, ey0 + 3), fill=c["stitch"])
        d.point((x + 1, ey0 + 3), fill=c["stitch"])

    # Tab: padded strap, its top half carries the snap / buckle.
    tx0, ty0, tx1, ty1 = R_TAB
    mid = tx0 + (tx1 - tx0) // 2
    d.rectangle([tx0, ty0, tx1 - 1, ty1 - 1], fill=c["dark"] if mat != "Cloth" else c["base"])
    stitch_rect(img, (tx0, ty0, mid, ty1), c["stitch"], inset=2, sides="lr")
    metal = {"metal": ((210, 208, 200), (140, 138, 132)), "brass": ((226, 192, 108), (150, 116, 52)),
             "plastic": ((80, 80, 76), (36, 36, 34))}[c["buckle"]]
    d.rectangle([tx0 + 3, ty0 + 3, mid - 4, ty0 + 9], fill=metal[1])
    d.rectangle([tx0 + 4, ty0 + 4, mid - 5, ty0 + 6], fill=metal[0])

    # Sides: a seam line along the middle, darker toward the bottom.
    sx0, sy0, sx1, sy1 = R_SIDES
    for y in range(sy0, sy1):
        k = 1.0 - 0.18 * (y - sy0) / (sy1 - sy0)
        for x in range(sx0, sx1):
            r, g, b, a = img.getpixel((x, y))
            img.putpixel((x, y), tone((r, g, b), k) + (255,))
    for x in range(sx0, sx1, 3):
        d.point((x, sy0 + 4), fill=c["stitch"])
        d.point((x + 1, sy0 + 4), fill=c["stitch"])

    # Bevels: shade the bottom one, light the top one.
    bx0, by0, bx1, by1 = R_BEVEL
    for y in range(by0, by1):
        k = 1.06 if y < by0 + 8 else 0.72
        for x in range(bx0, bx1):
            r, g, b, a = img.getpixel((x, y))
            img.putpixel((x, y), tone((r, g, b), k) + (255,))
    shade_edges(img, R_BACK, c["dark"])
    return img


def strap_texture(mat):
    """Pad in the material with quilting and bound edges, webbing at both ends, box-X stitching where they
    meet, hardware colours in the metal block."""
    c = MATERIALS[mat]
    rng = random.Random("strap" + mat)
    img = Image.new("RGBA", (TEX, TEX), c["dark"] + (255,))
    px = img.load()
    d = ImageDraw.Draw(img)
    pad_x0, pad_x1 = round(PAD_FROM * TEX), round(PAD_TO * TEX)

    # Webbing everywhere first: lengthwise weave lines.
    for y in range(0, 80):
        for x in range(TEX):
            k = 1.0 + rng.uniform(-0.04, 0.04) + (0.06 if y % 2 == 0 else -0.04)
            px[x, y] = tone(c["webbing"], k) + (255,)

    # Pad: the material on the top, sides and underside between the pad ends.
    for rect, shade_k in ((S_TOP, 1.0), (S_SIDE, 0.85), (S_BOTTOM, 0.8)):
        x0, y0, x1, y1 = rect
        fill_material(img, (pad_x0, y0, pad_x1, y1), mat, rng, "pad")
        if shade_k != 1.0:
            for y in range(y0, y1):
                for x in range(pad_x0, pad_x1):
                    r, g, b, a = px[x, y]
                    px[x, y] = tone((r, g, b), shade_k) + (255,)
    tx0, ty0, tx1, ty1 = S_TOP
    # bound edges along the pad, quilting lines down its length and across it
    d.rectangle([pad_x0, ty0, pad_x1 - 1, ty0 + 3], fill=c["dark"])
    d.rectangle([pad_x0, ty1 - 4, pad_x1 - 1, ty1 - 1], fill=c["dark"])
    for y in (ty0 + 6, ty1 - 7):
        for x in range(pad_x0 + 2, pad_x1 - 2):
            if x % 3 != 2:
                px[x, y] = c["stitch"] + (255,)
    for x in range(pad_x0 + 10, pad_x1 - 6, 10):
        for y in range(ty0 + 8, ty1 - 8):
            if y % 3 != 2:
                px[x, y] = tone(c["dark"], 1.05) + (255,)
    # the pad's end seams and the box-X stitching on the webbing beside each
    for x in (pad_x0, pad_x1 - 1):
        d.line([(x, ty0), (x, ty1 - 1)], fill=c["dark"])
    for bx in (pad_x0 - 9, pad_x1 + 2):
        y0, y1 = ty0 + 12, ty1 - 13
        d.rectangle([bx, y0, bx + 6, y1], outline=c["stitch"])
        d.line([(bx, y0), (bx + 6, y1)], fill=c["stitch"])
        d.line([(bx + 6, y0), (bx, y1)], fill=c["stitch"])

    # Hardware.
    metal = {"metal": ((214, 212, 204), (150, 148, 142), (100, 98, 94)),
             "brass": ((232, 198, 112), (176, 140, 64), (120, 92, 38)),
             "plastic": ((86, 86, 82), (58, 58, 56), (34, 34, 32))}[c["buckle"]]
    mx0, my0, mx1, my1 = S_METAL
    mid = (my0 + my1) // 2
    for y in range(my0, my1):
        for x in range(mx0, mx1):
            if y < mid:
                k = (y - my0) / (mid - my0)
                col = tuple(clamp(a + (b - a) * k) for a, b in zip(metal[0], metal[1]))
            else:
                col = metal[2]
            px[x, y] = col + (255,)
    return img


# --------------------------------------------------------------------------------------------------
# Item icons, rendered from the models
# --------------------------------------------------------------------------------------------------

OUTLINE = (26, 21, 18, 255)
ICON_VIEWS = {  # mesh, yaw, pitch
    "Capacity": (lambda: POUCH_OUT, "TienBagUpgrades_Pouch%s.png", 40.0, 38.0),
    "WeightReduction": (lambda: STRAP_ICON_MESH, "TienBagUpgrades_Strap%s.png", 30.0, 58.0),
}


def icon_from_model(mesh, texture, yaw, pitch):
    """A 32x32 item icon: the model rendered large, cropped, shrunk to fit 30 px, hard alpha edge, a little more
    contrast and colour so it reads at that size, and the 1 px near-black outline vanilla icons have."""
    big = pz_model.render(mesh, texture, size=384, yaw=yaw, pitch=pitch)
    big = big.crop(big.getchannel("A").getbbox())
    k = 30 / max(big.width, big.height)
    w, h = max(1, round(big.width * k)), max(1, round(big.height * k))
    small = big.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
    rgb = ImageEnhance.Color(ImageEnhance.Contrast(small.convert("RGB")).enhance(1.15)).enhance(1.1)
    alpha = small.getchannel("A").point(lambda a: 255 if a >= 110 else 0)
    small = rgb.convert("RGBA")
    small.putalpha(alpha)

    icon = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    icon.alpha_composite(small, ((32 - w) // 2, (32 - h) // 2))
    ap = icon.getchannel("A").load()
    px = icon.load()
    ring = []
    for y in range(32):
        for x in range(32):
            if ap[x, y]:
                continue
            if any(0 <= x + dx < 32 and 0 <= y + dy < 32 and ap[x + dx, y + dy]
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                ring.append((x, y))
    for p in ring:
        px[p] = OUTLINE
    return icon


STRAP_ICON_MESH = os.path.join(REPO, "tmp", "TienBagUpgrades_StrapCoiled.fbx")


def make_icons():
    write_mesh(build_strap(coiled=True), STRAP_ICON_MESH, "TienBagUpgrades_StrapCoiled")   # icon only, not shipped
    out = {}
    for kind, (mesh, tex, yaw, pitch) in ICON_VIEWS.items():
        for mat in MATERIALS:
            name = "Item_Upgrade%s%s" % (kind, mat)
            out[name] = icon_from_model(mesh(), os.path.join(TEX_OUT, tex % mat), yaw, pitch)
            out[name].save(os.path.join(ICON_OUT, name + ".png"))
    return out


PACKS = [os.path.join(PZ_MEDIA, "texturepacks", name) for name in ("UI2.pack", "UI.pack")]
_PACKS = {}


def pack_index(path):
    """name -> (page, x, y, w, h, offsetX, offsetY, originalW, originalH). A .pack is a run of
    int32-length-prefixed entry names, each followed by eight int32s, then once per page a plain
    PNG of the sheet; an entry belongs to the first PNG that starts after it."""
    if path in _PACKS:
        return _PACKS[path]
    if not os.path.exists(path):
        raise SystemExit("Missing game file: " + path)
    blob = open(path, "rb").read()
    pages = list(zip(
        [m.start() for m in re.finditer(rb"\x89PNG\r\n\x1a\n", blob)],
        [m.start() + 12 for m in re.finditer(rb"IEND\xaeB`\x82", blob)],
    ))
    index = {}
    for match in re.finditer(rb"[A-Za-z0-9_]{3,60}", blob):
        at, run = match.start(), match.group()
        if at < 4:
            continue
        length = struct.unpack_from("<i", blob, at - 4)[0]
        if not 3 <= length <= len(run):
            continue
        try:
            rect = struct.unpack_from("<8i", blob, at + length)
        except struct.error:
            continue
        page = next((i for i, p in enumerate(pages) if p[0] > at), None)
        if page is not None:
            index[run[:length].decode()] = (page,) + rect
    _PACKS[path] = {"blob": blob, "pages": pages, "sheets": {}, "index": index}
    return _PACKS[path]


def game_icon(name):
    for path in PACKS:
        pack = pack_index(path)
        if name not in pack["index"]:
            continue
        page, x, y, w, h, ox, oy, ow, oh = pack["index"][name]
        if page not in pack["sheets"]:
            start, end = pack["pages"][page]
            pack["sheets"][page] = Image.open(io.BytesIO(pack["blob"][start:end])).convert("RGBA")
        icon = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
        icon.paste(pack["sheets"][page].crop((x, y, x + w, y + h)), (ox, oy))
        return icon
    raise SystemExit("No icon named %s in UI2.pack or UI.pack" % name)


def icon_sheet(icons, path, zoom=6):
    """The icons zoomed, next to vanilla's fanny pack and belt, for checking by eye."""
    refs = [game_icon("Item_FannyPack"), game_icon("Item_Belt")]
    rows = [[icons["Item_UpgradeCapacity" + m] for m in MATERIALS] + refs[:1],
            [icons["Item_UpgradeWeightReduction" + m] for m in MATERIALS] + refs[1:]]
    cell = 34 * zoom
    sheet = Image.new("RGBA", (cell * 5, cell * 2), (58, 58, 58, 255))
    for r, row in enumerate(rows):
        for i, im in enumerate(row):
            sheet.alpha_composite(im.resize((32 * zoom, 32 * zoom), Image.NEAREST), (i * cell + zoom, r * cell + zoom))
    sheet.save(path)


def preview(path):
    tiles = []
    for mat in MATERIALS:
        tiles.append(pz_model.render(POUCH_OUT, os.path.join(TEX_OUT, "TienBagUpgrades_Pouch%s.png" % mat), size=256))
    for mat in MATERIALS:
        tiles.append(pz_model.render(STRAP_OUT, os.path.join(TEX_OUT, "TienBagUpgrades_Strap%s.png" % mat), size=256,
                                     zoom=1.2, pitch=40))
    sheet = Image.new("RGBA", (256 * 4, 256 * 2), (58, 58, 58, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % 4) * 256, (i // 4) * 256))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)


def main():
    counts = [write_mesh(build_pouch(), POUCH_OUT, "TienBagUpgrades_Pouch"),
              write_mesh(build_strap(), STRAP_OUT, "TienBagUpgrades_Strap")]
    os.makedirs(TEX_OUT, exist_ok=True)
    for mat in MATERIALS:
        pouch_texture(mat).save(os.path.join(TEX_OUT, "TienBagUpgrades_Pouch%s.png" % mat))
        strap_texture(mat).save(os.path.join(TEX_OUT, "TienBagUpgrades_Strap%s.png" % mat))
    print("Wrote the pouch (%d vertices, %d triangles) and strap (%d vertices, %d triangles) meshes and 8 textures"
          % (counts[0] + counts[1]))
    icons = make_icons()
    print("Wrote %d item icons" % len(icons))
    if "--preview" in sys.argv:
        out = os.path.join(REPO, "tmp", "models_preview.png")
        preview(out)
        icon_sheet(icons, os.path.join(REPO, "tmp", "icons_preview.png"))
        print("Previews: tmp/models_preview.png, tmp/icons_preview.png")


if __name__ == "__main__":
    main()
