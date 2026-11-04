"""
Export the rig to a binary STL, with no Fusion and no third-party packages.

    python cad/scripts/export_stl.py [output.stl]

Why this exists alongside the Fusion builder: the .f3d is the editable master,
but it is a proprietary binary nobody can inspect without a licence and an
Autodesk account. An STL generated from the same rig_spec.py gives anyone with
the repo something they can open, measure and sanity-check. If the two ever
disagree, rig_spec.py is wrong - it is the only place the geometry is defined.

Mesh quality is deliberately plain: flat facets, no smoothing, no boolean
union between parts. It is for looking at and measuring, not for printing or
analysis.

Author: VK12034
"""

import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_spec  # noqa: E402

SEGMENTS = 40


# --- axis mapping ---------------------------------------------------------
# Each primitive is generated in a local (u, v, w) frame where w runs along
# the part's own axis, then mapped into world xyz. Keeps one tessellation
# routine instead of three near-copies.

def _mapper(axis):
    if axis == "x":
        return lambda u, v, w: (w, u, v)
    if axis == "y":
        return lambda u, v, w: (u, w, v)
    if axis == "z":
        return lambda u, v, w: (u, v, w)
    raise ValueError("axis must be x, y or z, got %r" % axis)


def _centre_uvw(axis, centre):
    cx, cy, cz = centre
    if axis == "x":
        return cy, cz, cx
    if axis == "y":
        return cx, cz, cy
    return cx, cy, cz


def box_triangles(centre, size):
    cx, cy, cz = centre
    hx, hy, hz = (s / 2.0 for s in size)
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    z0, z1 = cz - hz, cz + hz
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (2, 3, 7), (2, 7, 6),
             (1, 2, 6), (1, 6, 5), (0, 4, 7), (0, 7, 3)]
    return [(v[i], v[j], v[k]) for i, j, k in faces]


def _ring(cu, cv, r, segments):
    return [(cu + r * math.cos(2 * math.pi * i / segments),
             cv + r * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]


def cyl_triangles(axis, centre, diameter, length, segments=SEGMENTS):
    m = _mapper(axis)
    cu, cv, cw = _centre_uvw(axis, centre)
    r = diameter / 2.0
    w0, w1 = cw - length / 2.0, cw + length / 2.0
    ring = _ring(cu, cv, r, segments)
    tris = []
    for i in range(segments):
        u0, v0 = ring[i]
        u1, v1 = ring[(i + 1) % segments]
        a, b = m(u0, v0, w0), m(u0, v0, w1)
        c, dd = m(u1, v1, w1), m(u1, v1, w0)
        tris.append((a, b, c))
        tris.append((a, c, dd))
        tris.append((m(cu, cv, w0), m(u1, v1, w0), m(u0, v0, w0)))
        tris.append((m(cu, cv, w1), m(u0, v0, w1), m(u1, v1, w1)))
    return tris


def tube_cyl_triangles(axis, centre, od, idia, length, segments=SEGMENTS):
    """Hollow cylinder: outer wall, inner wall, and two annular end faces."""
    m = _mapper(axis)
    cu, cv, cw = _centre_uvw(axis, centre)
    w0, w1 = cw - length / 2.0, cw + length / 2.0
    outer = _ring(cu, cv, od / 2.0, segments)
    inner = _ring(cu, cv, idia / 2.0, segments)
    tris = []
    for i in range(segments):
        j = (i + 1) % segments
        ou0, ov0 = outer[i]
        ou1, ov1 = outer[j]
        iu0, iv0 = inner[i]
        iu1, iv1 = inner[j]
        # outer wall
        tris.append((m(ou0, ov0, w0), m(ou0, ov0, w1), m(ou1, ov1, w1)))
        tris.append((m(ou0, ov0, w0), m(ou1, ov1, w1), m(ou1, ov1, w0)))
        # inner wall (reversed winding)
        tris.append((m(iu0, iv0, w0), m(iu1, iv1, w1), m(iu0, iv0, w1)))
        tris.append((m(iu0, iv0, w0), m(iu1, iv1, w0), m(iu1, iv1, w1)))
        # end annuli
        tris.append((m(iu0, iv0, w0), m(ou0, ov0, w0), m(ou1, ov1, w0)))
        tris.append((m(iu0, iv0, w0), m(ou1, ov1, w0), m(iu1, iv1, w0)))
        tris.append((m(iu0, iv0, w1), m(ou1, ov1, w1), m(ou0, ov0, w1)))
        tris.append((m(iu0, iv0, w1), m(iu1, iv1, w1), m(ou1, ov1, w1)))
    return tris


def gusset_triangles(plane, at, corner, legs, thickness):
    """Right-triangle prism, `thickness` centred on `at`."""
    u0, v0 = corner
    du, dv = legs
    tri2d = [(u0, v0), (u0 + du, v0), (u0, v0 + dv)]
    n0, n1 = at - thickness / 2.0, at + thickness / 2.0

    if plane == "yz":
        def put(u, v, n):
            return (n, u, v)
    elif plane == "xz":
        def put(u, v, n):
            return (u, n, v)
    elif plane == "xy":
        def put(u, v, n):
            return (u, v, n)
    else:
        raise ValueError("plane must be yz, xz or xy, got %r" % plane)

    a = [put(u, v, n0) for u, v in tri2d]
    b = [put(u, v, n1) for u, v in tri2d]
    tris = [(a[0], a[2], a[1]), (b[0], b[1], b[2])]
    for i in range(3):
        j = (i + 1) % 3
        tris.append((a[i], b[i], b[j]))
        tris.append((a[i], b[j], a[j]))
    return tris


def triangles_for(part):
    kind = part["kind"]
    if kind == "box":
        tris = box_triangles(part["centre"], part["size"])
    elif kind == "cyl":
        tris = cyl_triangles(part["axis"], part["centre"],
                             part["diameter"], part["length"])
    elif kind == "tube_cyl":
        tris = tube_cyl_triangles(part["axis"], part["centre"], part["od"],
                                  part["idia"], part["length"])
    elif kind == "gusset":
        tris = gusset_triangles(part["plane"], part["at"], part["corner"],
                                part["legs"], part["thickness"])
    else:
        raise ValueError("unknown primitive %r" % kind)

    rot = part.get("rot")
    if rot:
        tris = [tuple(rig_spec.rotate_point(v, rot) for v in tri) for tri in tris]
    return tris


def normal(tri):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (0.0, 0.0, 0.0) if mag == 0 else (nx / mag, ny / mag, nz / mag)


def write_binary_stl(path, tris, header_text):
    with open(path, "wb") as handle:
        header = header_text.encode("ascii", "replace")[:80]
        handle.write(header + b" " * (80 - len(header)))
        handle.write(struct.pack("<I", len(tris)))
        for tri in tris:
            handle.write(struct.pack("<3f", *normal(tri)))
            for vertex in tri:
                handle.write(struct.pack("<3f", *vertex))
            handle.write(struct.pack("<H", 0))


def bounds(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.normpath(
        os.path.join(here, "..", "exports", "tire_lift_mover_v1.stl")
    )
    out_path = argv[1] if len(argv) > 1 else default
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    envelope, source = rig_spec.load_envelope()
    part_list = rig_spec.parts(envelope)
    derived = rig_spec.derive(envelope)

    tris = []
    for part in part_list:
        tris.extend(triangles_for(part))

    write_binary_stl(out_path, tris, "ClearanceOS tire-lift mover v1 - TowFit")

    (xlo, xhi), (ylo, yhi), (zlo, zhi) = bounds(tris)
    components = []
    for part in part_list:
        if part["component"] not in components:
            components.append(part["component"])

    print("envelope source : %s" % source)
    print("parts           : %d across %d components"
          % (len(part_list), len(components)))
    print("triangles       : %d" % len(tris))
    print("bounding box mm : X %.1f..%.1f   Y %.1f..%.1f   Z %.1f..%.1f"
          % (xlo, xhi, ylo, yhi, zlo, zhi))
    print("overall mm      : %.0f wide x %.0f long x %.0f tall"
          % (xhi - xlo, yhi - ylo, zhi - zlo))
    print("mechanism       : arm %.0f mm at %.1f deg, ram %.0f mm at %.1f deg"
          % (derived["arm_run"], derived["arm_deg"],
             derived["ram_run"], derived["ram_deg"]))
    print("written         : %s (%.1f KB)"
          % (out_path, os.path.getsize(out_path) / 1024.0))

    print("\nper component")
    for name in components:
        n = sum(1 for p in part_list if p["component"] == name)
        print("  %-26s %3d parts" % (name, n))

    print("\nenvelope checks")
    failed = 0
    for label, ok, detail in rig_spec.checks(envelope):
        print("  [%s] %-46s %s" % ("PASS" if ok else "FAIL", label, detail))
        if not ok:
            failed += 1
    if failed:
        print("\n%d check(s) FAILED - geometry violates the rig envelope" % failed)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
