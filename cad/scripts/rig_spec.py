"""
ClearanceOS "tire-lift mover v1" - the single definition of the rig's geometry.

Pure Python. No Fusion, no third-party packages, so it can be imported by
anything: the Fusion builder (build_tire_lift_rig.py), the STL exporter
(export_stl.py), the drawing generator (export_views.py), or a test.

MECHANISM
---------
A pivoting L-arm wheel lift, which is how real tow rigs do this. A yoke on the
receiver carries a pivot. From that pivot a slanted arm drops down and forward
to a knee, and from the knee a horizontal boom runs under the vehicle to the
crossbeam. A hydraulic ram between a tower on the stinger and a lug partway
along the arm extends to rotate the whole assembly up about the pivot, lifting
the gripped tires off the road.

The earlier draft of this file used a vertical mast with a sliding carriage.
That was wrong - it is not how wheel lifts work, and it put a tall mast below
hitch height where it would drag.

WHY A SHARED SPEC
-----------------
The envelope numbers live in config/assumptions.yaml because the rule engine
checks vehicles against them. If the CAD carried its own copy, the two would
drift the first time the hardware team supplied a real number, and nobody
would notice until a RED verdict disagreed with a part that physically fits.

COORDINATES (millimetres)
-------------------------
  X  lateral, 0 = vehicle centreline, +X = driver's right
  Y  longitudinal, 0 = patrol car's hitch face, +Y = toward disabled vehicle
  Z  vertical, 0 = road surface

PRIMITIVES
----------
  box       axis-aligned rectangular prism
  cyl       cylinder about the x, y or z axis
  tube_cyl  hollow cylinder (ram barrel, roller shells, weld-in bushings)
  gusset    right-triangle prism in a named plane
  Box-section tubes are emitted as four walls rather than a hollow profile:
  four boxes are unambiguous in every consumer.

Any part may carry `rot` = {"axis", "deg", "pivot"}, applied after
construction. That is what places the slanted arm and the ram.

Nothing here has a load case. Section sizes are drawn for proportion.
"""

import math
import os
import re

UNIT = "patrol_42"

FALLBACK = {
    "rig_capacity_lb": 6000.0,
    "rig_tire_width_range_mm": [155.0, 315.0],
    "rig_min_ground_clearance_mm": 90.0,
    "rig_max_wheelbase_mm": 4000.0,
}

REPO_HINTS = [
    r"C:\Users\vishn\source\repos\TowFit-InnovateATL",
    os.path.expanduser("~/source/repos/TowFit-InnovateATL"),
]

# Fusion appearance library names, applied per component where available.
MATERIALS = {
    "01 Receiver Interface": "Steel - Satin",
    "02 Ram Tower": "Steel - Satin",
    "03 Pivot Yoke": "Steel - Satin",
    "04 Lift Arm": "Paint - Enamel Glossy (Yellow)",
    "05 Lift Ram": "Chrome Polished",
    "06 Lower Boom": "Paint - Enamel Glossy (Yellow)",
    "07 Main Crossbeam": "Paint - Enamel Glossy (Yellow)",
    "08 Telescoping Arms": "Steel - Satin",
    "09 Tire Cradles": "Steel - Satin",
    "10 Hydraulics": "Rubber",
}


# --------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------

def _find_assumptions():
    probe = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate = os.path.join(probe, "config", "assumptions.yaml")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    for hint in REPO_HINTS:
        candidate = os.path.join(hint, "config", "assumptions.yaml")
        if os.path.isfile(candidate):
            return candidate
    return None


def _parse_assumptions(text):
    """Read the registry's `- key: / value:` blocks.

    Fusion ships no PyYAML and this is not worth a dependency. The registry's
    shape is flat and fixed; if it ever grows nested structures this parser
    must be revisited rather than silently falling back.
    """
    found = {}
    for block in re.split(r"\n\s*-\s+key:\s*", "\n" + text)[1:]:
        key = block.splitlines()[0].strip()
        match = re.search(r"^\s*value:\s*(.+)$", block, re.M)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw.startswith("["):
            found[key] = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", raw)]
        else:
            try:
                found[key] = float(raw)
            except ValueError:
                found[key] = raw
    return found


def load_envelope():
    path = _find_assumptions()
    if not path:
        return dict(FALLBACK), "built-in fallback (config/assumptions.yaml not found)"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parsed = _parse_assumptions(handle.read())
    except OSError as exc:
        return dict(FALLBACK), "built-in fallback (registry unreadable: %s)" % exc

    envelope, missing = dict(FALLBACK), []
    for field in FALLBACK:
        key = "unit.%s.%s" % (UNIT, field)
        if key in parsed:
            envelope[field] = parsed[key]
        else:
            missing.append(key)
    note = path
    if missing:
        note += "  [fell back for: %s]" % ", ".join(missing)
    return envelope, note


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def _p(component, name, rot=None, **kw):
    part = {"component": component, "name": name}
    part.update(kw)
    if rot:
        part["rot"] = rot
    return part


def box(component, name, centre, size, rot=None):
    return _p(component, name, rot, kind="box",
              centre=tuple(map(float, centre)), size=tuple(map(float, size)))


def cyl(component, name, axis, centre, diameter, length, rot=None):
    return _p(component, name, rot, kind="cyl", axis=axis,
              centre=tuple(map(float, centre)),
              diameter=float(diameter), length=float(length))


def tube_cyl(component, name, axis, centre, od, idia, length, rot=None):
    return _p(component, name, rot, kind="tube_cyl", axis=axis,
              centre=tuple(map(float, centre)), od=float(od),
              idia=float(idia), length=float(length))


def gusset(component, name, plane, at, corner, legs, thickness, rot=None):
    """Right-triangle prism.

    plane "yz" -> u=Y, v=Z, extruded along X at x=`at`
    plane "xz" -> u=X, v=Z, extruded along Y at y=`at`
    plane "xy" -> u=X, v=Y, extruded along Z at z=`at`
    Triangle: (u,v), (u+legs[0], v), (u, v+legs[1]).
    """
    return _p(component, name, rot, kind="gusset", plane=plane, at=float(at),
              corner=tuple(map(float, corner)), legs=tuple(map(float, legs)),
              thickness=float(thickness))


def box_tube(component, name, centre, section, length, axis, wall, rot=None):
    """Box-section tube as four walls.

    `section` is the pair of dimensions perpendicular to `axis`:
      axis x -> (sy, sz)      axis y -> (sx, sz)      axis z -> (sx, sy)
    """
    cx, cy, cz = centre
    a, b = section
    out = []
    if axis == "x":
        inner = b - 2 * wall
        out.append(box(component, name + "_top", (cx, cy, cz + b / 2 - wall / 2), (length, a, wall), rot))
        out.append(box(component, name + "_bot", (cx, cy, cz - b / 2 + wall / 2), (length, a, wall), rot))
        out.append(box(component, name + "_web_n", (cx, cy - a / 2 + wall / 2, cz), (length, wall, inner), rot))
        out.append(box(component, name + "_web_p", (cx, cy + a / 2 - wall / 2, cz), (length, wall, inner), rot))
    elif axis == "y":
        inner = b - 2 * wall
        out.append(box(component, name + "_top", (cx, cy, cz + b / 2 - wall / 2), (a, length, wall), rot))
        out.append(box(component, name + "_bot", (cx, cy, cz - b / 2 + wall / 2), (a, length, wall), rot))
        out.append(box(component, name + "_web_n", (cx - a / 2 + wall / 2, cy, cz), (wall, length, inner), rot))
        out.append(box(component, name + "_web_p", (cx + a / 2 - wall / 2, cy, cz), (wall, length, inner), rot))
    elif axis == "z":
        inner = b - 2 * wall
        out.append(box(component, name + "_xn", (cx - a / 2 + wall / 2, cy, cz), (wall, b, length), rot))
        out.append(box(component, name + "_xp", (cx + a / 2 - wall / 2, cy, cz), (wall, b, length), rot))
        out.append(box(component, name + "_yn", (cx, cy - b / 2 + wall / 2, cz), (a - 2 * wall, wall, length), rot))
        out.append(box(component, name + "_yp", (cx, cy + b / 2 - wall / 2, cz), (a - 2 * wall, wall, length), rot))
    else:
        raise ValueError("axis must be x, y or z, got %r" % axis)
    return out


def part_bounds(part):
    """Conservative axis-aligned bounds for one part, in mm.

    Rotation is handled by rotating the eight corners of the unrotated box and
    re-bounding, which over-estimates for an angled member but never
    under-estimates - the right direction to err for a clearance check.
    """
    kind = part["kind"]
    if kind == "box":
        cx, cy, cz = part["centre"]
        sx, sy, sz = part["size"]
    elif kind in ("cyl", "tube_cyl"):
        cx, cy, cz = part["centre"]
        dia = part["od"] if kind == "tube_cyl" else part["diameter"]
        length = part["length"]
        if part["axis"] == "x":
            sx, sy, sz = length, dia, dia
        elif part["axis"] == "y":
            sx, sy, sz = dia, length, dia
        else:
            sx, sy, sz = dia, dia, length
    elif kind == "gusset":
        u0, v0 = part["corner"]
        du, dv = part["legs"]
        ulo, uhi = min(u0, u0 + du), max(u0, u0 + du)
        vlo, vhi = min(v0, v0 + dv), max(v0, v0 + dv)
        t = part["thickness"]
        if part["plane"] == "yz":
            cx, cy, cz = part["at"], (ulo + uhi) / 2, (vlo + vhi) / 2
            sx, sy, sz = t, uhi - ulo, vhi - vlo
        elif part["plane"] == "xz":
            cx, cy, cz = (ulo + uhi) / 2, part["at"], (vlo + vhi) / 2
            sx, sy, sz = uhi - ulo, t, vhi - vlo
        else:
            cx, cy, cz = (ulo + uhi) / 2, (vlo + vhi) / 2, part["at"]
            sx, sy, sz = uhi - ulo, vhi - vlo, t
    else:
        raise ValueError("unknown primitive %r" % kind)

    corners = [
        (cx + i * sx / 2, cy + j * sy / 2, cz + k * sz / 2)
        for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)
    ]
    rot = part.get("rot")
    if rot:
        corners = [rotate_point(c, rot) for c in corners]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def envelope_bounds(part_list):
    """Overall bounds across every part."""
    xlo = ylo = zlo = float("inf")
    xhi = yhi = zhi = float("-inf")
    for part in part_list:
        (a, b), (c, dd), (e, f) = part_bounds(part)
        xlo, xhi = min(xlo, a), max(xhi, b)
        ylo, yhi = min(ylo, c), max(yhi, dd)
        zlo, zhi = min(zlo, e), max(zhi, f)
    return (xlo, xhi), (ylo, yhi), (zlo, zhi)


def rotate_point(point, rot):
    """Apply a `rot` dict to an (x, y, z) tuple. Shared so every consumer
    places parts identically."""
    if not rot:
        return point
    x, y, z = point
    px, py, pz = rot["pivot"]
    t = math.radians(rot["deg"])
    c, s = math.cos(t), math.sin(t)
    dx, dy, dz = x - px, y - py, z - pz
    if rot["axis"] == "x":
        ny, nz = dy * c - dz * s, dy * s + dz * c
        nx = dx
    elif rot["axis"] == "y":
        nz, nx = dz * c - dx * s, dz * s + dx * c
        ny = dy
    else:
        nx, ny = dx * c - dy * s, dx * s + dy * c
        nz = dz
    return (px + nx, py + ny, pz + nz)


# --------------------------------------------------------------------------
# Derived dimensions
# --------------------------------------------------------------------------

def derive(envelope):
    """Everything the geometry needs, with provenance made explicit.

    Values tagged 'envelope' trace to config/assumptions.yaml. Values tagged
    'concept' are the author's estimates: not sourced, not analysed.
    """
    tire_min, tire_max = envelope["rig_tire_width_range_mm"]
    min_clearance = envelope["rig_min_ground_clearance_mm"]

    road_gap = 20.0
    safety = 10.0
    beam_h = min_clearance - road_gap - safety     # the binding constraint

    d = {
        # --- traceable to the registry ---
        "capacity_lb": envelope["rig_capacity_lb"],
        "tire_min": tire_min,
        "tire_max": tire_max,
        "min_clearance": min_clearance,
        "max_wheelbase": envelope["rig_max_wheelbase_mm"],
        "beam_h": beam_h,
        "roller_len": tire_max + 45.0,
        # --- concept estimates, not sourced ---
        "road_gap": road_gap,
        "safety": safety,
        "beam_w": 100.0,
        "beam_len": 1400.0,
        "wall": 6.0,
        "roller_od": 90.0,
        "roller_gap": 220.0,
        "shaft_d": 30.0,
        "hitch_h": 400.0,
        "stinger": 50.8,
        "stinger_len": 420.0,
        "track": 1550.0,
        "lift_stroke": 150.0,
        "arm_len": 600.0,
        "arm_ext": 250.0,
    }

    # Mechanism control points
    d["beam_z"] = road_gap + beam_h / 2.0          # 50 mm
    d["pivot"] = (0.0, 190.0, 390.0)
    d["knee_y"] = 330.0
    d["beam_y"] = 560.0
    d["ram_anchor"] = (0.0, 20.0, 505.0)

    # Slanted lift arm: pivot -> knee
    dy = d["knee_y"] - d["pivot"][1]
    dz = d["beam_z"] - d["pivot"][2]
    d["arm_run"] = math.hypot(dy, dz)
    d["arm_deg"] = math.degrees(math.atan2(dz, dy))

    # Ram: anchor -> lug at 45% along the arm
    d["ram_frac"] = 0.45
    lug_unrot = (0.0, d["pivot"][1] + d["ram_frac"] * d["arm_run"], d["pivot"][2])
    arm_rot = {"axis": "x", "deg": d["arm_deg"], "pivot": d["pivot"]}
    lug = rotate_point(lug_unrot, arm_rot)
    d["ram_lug"] = lug
    rdy = lug[1] - d["ram_anchor"][1]
    rdz = lug[2] - d["ram_anchor"][2]
    d["ram_run"] = math.hypot(rdy, rdz)
    d["ram_deg"] = math.degrees(math.atan2(rdz, rdy))
    d["arm_rot"] = arm_rot
    d["ram_rot"] = {"axis": "x", "deg": d["ram_deg"], "pivot": d["ram_anchor"]}
    d["ram_lug_unrot"] = lug_unrot
    return d


# --------------------------------------------------------------------------
# The rig
# --------------------------------------------------------------------------

def parts(envelope=None):
    if envelope is None:
        envelope, _ = load_envelope()
    d = derive(envelope)
    out = []
    add = out.append
    ext = out.extend

    hz = d["hitch_h"]
    st = d["stinger"]
    beam_z = d["beam_z"]
    beam_y = d["beam_y"]
    bh, bw, wall = d["beam_h"], d["beam_w"], d["wall"]
    half_beam = d["beam_len"] / 2.0

    # ===== 01 Receiver Interface ========================================
    C = "01 Receiver Interface"
    ext(box_tube(C, "stinger", (0, -100, hz), (st, st), 420, "y", 6))
    add(cyl(C, "hitch_pin", "x", (0, -250, hz), 16, 86))
    add(cyl(C, "hitch_pin_head", "x", (46, -250, hz), 28, 10))
    add(cyl(C, "pin_clip", "z", (-46, -250, hz), 7, 46))
    add(box(C, "mount_plate", (0, 126, hz), (270, 20, 300)))
    for sx in (-1, 1):
        add(gusset(C, "gus_top_%d" % sx, "yz", sx * 34, (116, hz + 26), (-100, 92), 10))
        add(gusset(C, "gus_bot_%d" % sx, "yz", sx * 34, (116, hz - 26), (-100, -92), 10))
    for sx in (-1, 1):
        for zz in (hz - 95, hz, hz + 95):
            add(cyl(C, "boss_%d_%d" % (sx, int(zz)), "y", (sx * 100, 140, zz), 24, 22))
            add(cyl(C, "bolt_%d_%d" % (sx, int(zz)), "y", (sx * 100, 154, zz), 16, 14))
        add(box(C, "chain_lug_%d" % sx, (sx * 118, 112, hz - 118), (14, 44, 58)))
        add(tube_cyl(C, "chain_eye_%d" % sx, "x", (sx * 118, 112, hz - 132), 34, 20, 14))

    # ===== 02 Ram Tower =================================================
    C = "02 Ram Tower"
    ext(box_tube(C, "post", (0, 20, 473), (64, 64), 96, "z", 6))
    add(box(C, "post_cap", (0, 20, 523), (76, 76, 10)))
    for sx in (-1, 1):
        add(box(C, "tower_lug_%d" % sx, (sx * 20, 20, 505), (14, 56, 56)))
        add(gusset(C, "tower_gus_%d" % sx, "yz", sx * 24, (52, 428), (-64, 56), 8))
    add(cyl(C, "tower_pin", "x", d["ram_anchor"], 22, 64))

    # ===== 03 Pivot Yoke ================================================
    C = "03 Pivot Yoke"
    px, py, pz = d["pivot"]
    for sx in (-1, 1):
        add(box(C, "yoke_plate_%d" % sx, (sx * 62, 168, pz), (16, 96, 120)))
        add(gusset(C, "yoke_gus_%d" % sx, "yz", sx * 62, (138, pz + 36), (-18, 54), 10))
        add(tube_cyl(C, "yoke_bush_%d" % sx, "x", (sx * 54, py, pz), 48, 30, 18))
    add(cyl(C, "pivot_pin", "x", (0, py, pz), 30, 170))
    for sx in (-1, 1):
        add(cyl(C, "pivot_pin_head_%d" % sx, "x", (sx * 88, py, pz), 46, 10))

    # ===== 04 Lift Arm (rotated about the pivot) ========================
    C = "04 Lift Arm"
    R = d["arm_rot"]
    arm_cy = py + d["arm_run"] / 2.0
    ext(box_tube(C, "arm", (0, arm_cy, pz), (96, 118), d["arm_run"], "y", 8, R))
    add(tube_cyl(C, "arm_pivot_boss", "x", (0, py, pz), 76, 30, 104, R))
    add(box(C, "arm_knee_plate", (0, py + d["arm_run"] - 6, pz), (120, 14, 140), R))
    lug_y = d["ram_lug_unrot"][1]
    for sx in (-1, 1):
        add(box(C, "arm_ram_lug_%d" % sx, (sx * 30, lug_y, pz + 44), (16, 86, 70), R))
        add(gusset(C, "arm_gus_%d" % sx, "yz", sx * 52, (py + 80, pz + 59), (120, -34), 8, R))
    add(cyl(C, "arm_ram_pin", "x", (0, lug_y, pz + 62), 24, 96, R))
    for sx in (-1, 1):
        add(tube_cyl(C, "arm_ram_bush_%d" % sx, "x", (sx * 26, lug_y, pz + 62), 40, 24, 14, R))

    # ===== 05 Lift Ram (rotated about its anchor) =======================
    C = "05 Lift Ram"
    R = d["ram_rot"]
    ay = d["ram_anchor"][1]
    az = d["ram_anchor"][2]
    barrel_len = d["ram_run"] * 0.62
    add(tube_cyl(C, "barrel", "y", (0, ay + 16 + barrel_len / 2.0, az), 92, 72, barrel_len, R))
    add(cyl(C, "barrel_cap_rear", "y", (0, ay + 14, az), 100, 18, R))
    add(cyl(C, "barrel_cap_front", "y", (0, ay + 18 + barrel_len, az), 100, 20, R))
    rod_start = ay + 18 + barrel_len
    rod_len = d["ram_run"] - (rod_start - ay) - 26
    add(cyl(C, "rod", "y", (0, rod_start + rod_len / 2.0, az), 42, rod_len, R))
    add(box(C, "rod_eye", (0, ay + d["ram_run"] - 14, az), (52, 40, 56), R))
    add(tube_cyl(C, "rod_eye_bush", "x", (0, ay + d["ram_run"] - 14, az), 40, 24, 54, R))
    for sx in (-1, 1):
        add(box(C, "rear_clevis_%d" % sx, (sx * 24, ay + 6, az), (16, 48, 56), R))
    for frac, tag in ((0.12, "lo"), (0.78, "hi")):
        porty = ay + 20 + barrel_len * frac
        add(cyl(C, "port_%s" % tag, "z", (0, porty, az + 60), 20, 44, R))
        add(cyl(C, "fitting_%s" % tag, "z", (0, porty, az + 84), 26, 16, R))

    # ===== 06 Lower Boom ================================================
    C = "06 Lower Boom"
    boom_len = beam_y - d["knee_y"]
    ext(box_tube(C, "boom", (0, d["knee_y"] + boom_len / 2.0, beam_z), (bw, bh), boom_len, "y", wall))
    for sx in (-1, 1):
        add(box(C, "knee_plate_%d" % sx, (sx * 56, d["knee_y"] + 30, beam_z + 25), (14, 76, 100)))
        add(gusset(C, "knee_gus_%d" % sx, "yz", sx * 40, (d["knee_y"] + 10, beam_z + 30), (90, -46), 8))

    # ===== 07 Main Crossbeam ============================================
    C = "07 Main Crossbeam"
    ext(box_tube(C, "crossbeam", (0, beam_y, beam_z), (bw, bh), d["beam_len"], "x", wall))
    for sx in (-1, 1):
        add(box(C, "end_cap_%d" % sx, (sx * (half_beam + 4), beam_y, beam_z), (8, bw, bh)))
    add(box(C, "saddle", (0, beam_y, beam_z + bh / 2 + 8), (200, 120, 16)))
    for sx in (-1, 1):
        add(gusset(C, "saddle_gus_%d" % sx, "xz", beam_y + sx * 52,
                   (sx * 90, beam_z + bh / 2), (sx * 70, 36), 8))
    for sx in (-1, 1):
        for xx in (340, 450, 560):
            # Seated on the beam's underside and protruding only upward, so a
            # weld-in bushing never becomes the lowest thing on the rig.
            add(tube_cyl(C, "detent_%d_%d" % (sx, xx), "z",
                         (sx * xx, beam_y, beam_z + 3), 26, 15, bh + 6))

    # ===== 08 Telescoping Arms ==========================================
    C = "08 Telescoping Arms"
    arm_sy, arm_sz = bw - 2 * wall - 4, bh - 2 * wall - 4
    for sx in (-1, 1):
        acx = sx * (half_beam - d["arm_len"] / 2.0 + d["arm_ext"])
        ext(box_tube(C, "tarm_%d" % sx, (acx, beam_y, beam_z), (arm_sy, arm_sz), d["arm_len"], "x", 5))
        tip = sx * (half_beam + d["arm_ext"])
        add(box(C, "tarm_stop_%d" % sx, (tip - sx * 10, beam_y, beam_z), (20, arm_sy + 14, arm_sz + 12)))
        add(cyl(C, "tarm_handle_%d" % sx, "z", (tip - sx * 40, beam_y, beam_z + 54), 22, 70))
        add(cyl(C, "tarm_grip_%d" % sx, "x", (tip - sx * 40, beam_y, beam_z + 84), 26, 90))
        for xx in (430, 530, 630):
            add(tube_cyl(C, "tdetent_%d_%d" % (sx, xx), "z", (sx * xx, beam_y, beam_z), 22, 14, arm_sz + 4))

    # ===== 09 Tire Cradles ==============================================
    C = "09 Tire Cradles"
    roller_r = d["roller_od"] / 2.0
    roller_z = d["road_gap"] + roller_r
    cradle_cy = beam_y + 220.0
    # Kept tight to the roller length: the cradle frame should not make the
    # rig wider than the vehicle it is straddling.
    plate_dx = d["roller_len"] / 2.0 + 14.0
    for sx in (-1, 1):
        cx = sx * (d["track"] / 2.0)
        add(box(C, "cradle_mount_%d" % sx, (cx, beam_y + 24, beam_z), (d["roller_len"] + 20, 48, arm_sz + 6)))
        add(box(C, "cradle_spine_%d" % sx, (cx, beam_y + 110, beam_z + 4), (d["roller_len"] + 40, 130, 26)))
        for sgn, tag in ((-1, "aft"), (1, "fwd")):
            ry = cradle_cy + sgn * d["roller_gap"] / 2.0
            add(cyl(C, "shaft_%d_%s" % (sx, tag), "x", (cx, ry, roller_z), d["shaft_d"], d["roller_len"] + 30))
            add(tube_cyl(C, "roller_%d_%s" % (sx, tag), "x", (cx, ry, roller_z),
                         d["roller_od"], d["shaft_d"] + 4, d["roller_len"]))
            for px2 in (-1, 1):
                add(box(C, "brg_%d_%s_%d" % (sx, tag, px2),
                        (cx + px2 * plate_dx, ry, roller_z), (30, 76, 76)))
                add(cyl(C, "brgcap_%d_%s_%d" % (sx, tag, px2), "x",
                        (cx + px2 * plate_dx, ry, roller_z), 52, 34))
        for px2 in (-1, 1):
            add(box(C, "plate_%d_%d" % (sx, px2), (cx + px2 * plate_dx, cradle_cy, 88),
                    (16, d["roller_gap"] + d["roller_od"] + 70, 132)))
            # Gusset leans inboard, not outboard, for the same width reason.
            add(gusset(C, "cradle_gus_%d_%d" % (sx, px2), "xz", cradle_cy - 150,
                       (cx + px2 * plate_dx, beam_z + 22), (-px2 * 40, 60), 10))
        add(box(C, "tie_top_%d" % sx, (cx, cradle_cy, 150), (d["roller_len"] + 40, 44, 18)))
        for sgn in (-1, 1):
            add(box(C, "pad_%d_%d" % (sx, sgn), (cx, cradle_cy + sgn * 190, 60), (d["roller_len"], 16, 70)))

    # ===== 10 Hydraulics ================================================
    C = "10 Hydraulics"
    for sx in (-1, 1):
        add(cyl(C, "hose_%d" % sx, "y", (sx * 36, -40, hz + 86), 16, 230))
        add(cyl(C, "hose_bend_%d" % sx, "z", (sx * 36, 72, hz + 120), 16, 90))
        add(cyl(C, "hose_fit_%d" % sx, "z", (sx * 36, 72, hz + 170), 24, 20))
    return out


def checks(envelope=None):
    """Assertions tying the geometry back to the envelope it must respect."""
    if envelope is None:
        envelope, _ = load_envelope()
    d = derive(envelope)
    beam_top = d["road_gap"] + d["beam_h"]
    return [
        ("beam fits under min ground clearance",
         beam_top <= d["min_clearance"],
         "%.0f mm beam top vs %.0f mm clearance" % (beam_top, d["min_clearance"])),
        ("rollers span the widest gripped tire",
         d["roller_len"] >= d["tire_max"],
         "%.0f mm roller vs %.0f mm tire" % (d["roller_len"], d["tire_max"])),
        ("rollers still support the narrowest gripped tire",
         d["roller_len"] >= d["tire_min"],
         "%.0f mm roller vs %.0f mm tire" % (d["roller_len"], d["tire_min"])),
        ("beam spans a typical axle track",
         d["beam_len"] + 2 * d["arm_ext"] >= d["track"],
         "%.0f mm extended vs %.0f mm track" % (d["beam_len"] + 2 * d["arm_ext"], d["track"])),
        ("arms clear the beam's internal section",
         d["beam_h"] - 2 * d["wall"] - 4 > 0,
         "%.0f mm arm height" % (d["beam_h"] - 2 * d["wall"] - 4)),
        ("ram reaches its lug from the tower anchor",
         150.0 < d["ram_run"] < 600.0,
         "%.0f mm closed length" % d["ram_run"]),
    ] + _geometry_checks(envelope, d)


def _geometry_checks(envelope, d):
    """Checks that look at where every part actually ended up.

    The envelope checks above compare numbers to numbers, which cannot catch a
    bracket that was placed too low or a frame that quietly grew wider than
    the vehicle. These measure the built geometry instead.
    """
    part_list = parts(envelope)
    (xlo, xhi), (_, yhi), (zlo, _) = envelope_bounds(part_list)

    # A rig that straddles the track and grips a tire this wide CANNOT be
    # narrower than track + roller length; the only thing worth policing is
    # frame bloat on top of that. An absolute number here would either fail
    # on geometry the envelope demands or pass anything.
    # 90 mm covers side plates, bearing caps and shaft ends on both sides.
    max_width = d["track"] + d["roller_len"] + 90.0

    return [
        ("nothing hangs below the road gap",
         zlo >= d["road_gap"] - 0.5,
         "lowest part at %.0f mm vs %.0f mm gap" % (zlo, d["road_gap"])),
        ("rig stays within a sane overall width",
         (xhi - xlo) <= max_width,
         "%.0f mm wide vs %.0f mm limit" % (xhi - xlo, max_width)),
        ("cradles reach past the axle to grip the tires",
         yhi >= d["beam_y"] + d["roller_gap"],
         "reach %.0f mm vs beam at %.0f mm" % (yhi, d["beam_y"])),
    ]
