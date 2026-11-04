"""
Export the rig to a binary STL, with no Fusion and no third-party packages.

    python cad/scripts/export_stl.py [output.stl]

Why this exists alongside the Fusion builder: the .f3d is the editable master,
but it is a proprietary binary nobody can inspect without a licence and an
Autodesk account. An STL generated from the same rig_spec.py gives anyone with
the repo something they can open, measure and sanity-check. If the two ever
disagree, rig_spec.py is wrong - it is the only place the geometry is defined.

Mesh quality is deliberately plain: flat facets, no normals smoothing, no
boolean union between parts. It is for looking at and measuring, not for
printing or analysis.

Author: VK12034
"""

import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_spec  # noqa: E402

CYL_SEGMENTS = 48


def _tri(a, b, c):
    return (a, b, c)


def box_triangles(centre, size):
    cx, cy, cz = centre
    hx, hy, hz = (s / 2.0 for s in size)
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    z0, z1 = cz - hz, cz + hz

    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [
        (0, 2, 1), (0, 3, 2),   # bottom
        (4, 5, 6), (4, 6, 7),   # top
        (0, 1, 5), (0, 5, 4),   # -Y
        (2, 3, 7), (2, 7, 6),   # +Y
        (1, 2, 6), (1, 6, 5),   # +X
        (0, 4, 7), (0, 7, 3),   # -X
    ]
    return [_tri(v[i], v[j], v[k]) for i, j, k in faces]


def cyl_x_triangles(centre, diameter, length, segments=CYL_SEGMENTS):
    """Cylinder with its axis along X."""
    cx, cy, cz = centre
    r = diameter / 2.0
    x0, x1 = cx - length / 2.0, cx + length / 2.0

    ring = []
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        ring.append((cy + r * math.cos(theta), cz + r * math.sin(theta)))

    tris = []
    for i in range(segments):
        y0, z0 = ring[i]
        y1, z1 = ring[(i + 1) % segments]
        # side
        tris.append(_tri((x0, y0, z0), (x1, y0, z0), (x1, y1, z1)))
        tris.append(_tri((x0, y0, z0), (x1, y1, z1), (x0, y1, z1)))
        # caps
        tris.append(_tri((x0, cy, cz), (x0, y1, z1), (x0, y0, z0)))
        tris.append(_tri((x1, cy, cz), (x1, y0, z0), (x1, y1, z1)))
    return tris


def normal(tri):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (0.0, 0.0, 0.0) if mag == 0 else (nx / mag, ny / mag, nz / mag)


def triangles_for(part):
    if part["kind"] == "box":
        return box_triangles(part["centre"], part["size"])
    if part["kind"] == "cyl_x":
        return cyl_x_triangles(part["centre"], part["diameter"], part["length"])
    raise ValueError("unknown primitive %r" % part["kind"])


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
    print("parts           : %d across %d components" % (len(part_list), len(components)))
    print("triangles       : %d" % len(tris))
    print("bounding box mm : X %.1f..%.1f   Y %.1f..%.1f   Z %.1f..%.1f"
          % (xlo, xhi, ylo, yhi, zlo, zhi))
    print("overall mm      : %.0f wide x %.0f long x %.0f tall"
          % (xhi - xlo, yhi - ylo, zhi - zlo))
    print("written         : %s (%.1f KB)"
          % (out_path, os.path.getsize(out_path) / 1024.0))

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
