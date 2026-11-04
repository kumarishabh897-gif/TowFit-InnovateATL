"""
ClearanceOS "tire-lift mover v1" - the single definition of the rig's geometry.

Pure Python. No Fusion, no third-party packages, so it can be imported by
anything: the Fusion builder (build_tire_lift_rig.py), the STL exporter
(export_stl.py), or a test.

WHY A SHARED SPEC
-----------------
The envelope numbers live in config/assumptions.yaml because the rule engine
checks vehicles against them. If the CAD carried its own copy, the two would
drift the first time the hardware team supplied a real number, and nobody
would notice until a RED verdict disagreed with a part that physically fits.
So the geometry is derived here, once, from that file.

COORDINATES (millimetres)
-------------------------
  X  lateral, 0 = vehicle centreline, +X = driver's right
  Y  longitudinal, 0 = patrol car's hitch face, +Y = toward disabled vehicle
  Z  vertical, 0 = road surface

PRIMITIVES
----------
  box    axis-aligned rectangular prism: centre (x,y,z), size (sx,sy,sz)
  cyl_x  cylinder whose axis runs along X: centre, diameter, length

A box-section tube is emitted as its four walls rather than as a hollow
profile. Four boxes are unambiguous in every consumer, where a "ring profile"
has to be picked out of a sketch by loop count and is easy to get wrong.
"""

import os
import re

UNIT = "patrol_42"

# Mirrors config/assumptions.yaml at time of writing, so this module still
# runs if it is ever copied somewhere without the repo around it.
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
    """Return (envelope, source_description)."""
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
# Geometry
# --------------------------------------------------------------------------

def box(component, name, centre, size):
    return {"kind": "box", "component": component, "name": name,
            "centre": tuple(float(v) for v in centre),
            "size": tuple(float(v) for v in size)}


def cyl_x(component, name, centre, diameter, length):
    return {"kind": "cyl_x", "component": component, "name": name,
            "centre": tuple(float(v) for v in centre),
            "diameter": float(diameter), "length": float(length)}


def box_tube(component, name, centre, section, length, axis, wall):
    """Box-section tube as four walls.

    `section` is the cross-section (across, tall) in mm, perpendicular to
    `axis`; `length` runs along `axis`. Emitted as four solid boxes so no
    consumer has to interpret a hollow profile.
    """
    cx, cy, cz = centre
    across, tall = section
    inner_tall = tall - 2 * wall
    parts = []

    if axis == "x":
        parts.append(box(component, name + "_top", (cx, cy, cz + tall / 2 - wall / 2), (length, across, wall)))
        parts.append(box(component, name + "_bot", (cx, cy, cz - tall / 2 + wall / 2), (length, across, wall)))
        parts.append(box(component, name + "_web_n", (cx, cy - across / 2 + wall / 2, cz), (length, wall, inner_tall)))
        parts.append(box(component, name + "_web_p", (cx, cy + across / 2 - wall / 2, cz), (length, wall, inner_tall)))
    elif axis == "y":
        parts.append(box(component, name + "_top", (cx, cy, cz + tall / 2 - wall / 2), (across, length, wall)))
        parts.append(box(component, name + "_bot", (cx, cy, cz - tall / 2 + wall / 2), (across, length, wall)))
        parts.append(box(component, name + "_web_n", (cx - across / 2 + wall / 2, cy, cz), (wall, length, inner_tall)))
        parts.append(box(component, name + "_web_p", (cx + across / 2 - wall / 2, cy, cz), (wall, length, inner_tall)))
    else:
        raise ValueError("axis must be 'x' or 'y', got %r" % axis)

    return parts


def derive(envelope):
    """Everything the geometry needs, with its provenance made explicit.

    Values tagged 'envelope' trace to config/assumptions.yaml. Values tagged
    'concept' are the author's estimates: not sourced, not analysed, not in
    the registry.
    """
    tire_min, tire_max = envelope["rig_tire_width_range_mm"]
    min_clearance = envelope["rig_min_ground_clearance_mm"]

    road_gap = 20.0        # concept: clearance left under the beam on the road
    safety = 10.0          # concept: margin against the vehicle's underside

    # The beam passes UNDER the lowest vehicle the rig claims to serve, so
    # beam height + road gap must stay inside min_ground_clearance.
    beam_h = min_clearance - road_gap - safety

    return {
        # --- traceable to the registry ---
        "capacity_lb": envelope["rig_capacity_lb"],
        "tire_min": tire_min,
        "tire_max": tire_max,
        "min_clearance": min_clearance,
        "max_wheelbase": envelope["rig_max_wheelbase_mm"],
        "beam_h": beam_h,                      # derived from clearance
        "roller_len": tire_max + 45.0,         # derived from widest tire
        # --- concept estimates, not sourced ---
        "road_gap": road_gap,
        "safety": safety,
        "beam_w": 100.0,
        "beam_len": 1400.0,
        "wall": 6.0,
        "roller_dia": 90.0,
        "roller_gap": 220.0,
        "hitch_h": 400.0,
        "stinger": 50.8,                       # 2 in square receiver
        "stinger_len": 420.0,
        "mast_h": 460.0,
        "boom_y0": 195.0,
        "boom_y1": 560.0,
        "beam_y": 560.0,
        "track": 1550.0,
        "lift_stroke": 150.0,
        "arm_len": 600.0,
        "arm_ext": 250.0,
    }


def parts(envelope=None):
    """Return the full part list for the rig, in its lowered position."""
    if envelope is None:
        envelope, _ = load_envelope()
    d = derive(envelope)

    beam_z = d["road_gap"] + d["beam_h"] / 2.0
    half_beam = d["beam_len"] / 2.0
    out = []

    # -- 01 Receiver interface -------------------------------------------
    out.append(box("01 Receiver Stinger", "stinger",
                   (0, -100, d["hitch_h"]),
                   (d["stinger"], d["stinger_len"], d["stinger"])))
    out.append(box("01 Receiver Stinger", "pin_plate",
                   (0, 120, d["hitch_h"]), (160, 16, 160)))

    # -- 02 Mast: the rail the lift carriage travels on -------------------
    mast_cz = 80 + d["mast_h"] / 2.0
    for side, tag in ((-1, "L"), (1, "R")):
        out.append(box("02 Mast", "mast_rail_%s" % tag,
                       (side * 70, 150, mast_cz), (18, 90, d["mast_h"])))
    out.append(box("02 Mast", "mast_cap", (0, 150, 80 + d["mast_h"]), (158, 90, 18)))

    # -- 03 Lift actuator (representation, not a sized cylinder) ----------
    out.append(box("03 Lift Actuator", "cylinder_body", (0, 150, 220), (80, 80, 200)))
    out.append(box("03 Lift Actuator", "rod", (0, 150, 360), (36, 36, 120)))
    out.append(box("03 Lift Actuator", "carriage", (0, 150, beam_z + 30), (190, 76, 90)))

    # -- 04 Reach boom: carries the beam forward under the vehicle --------
    boom_len = d["boom_y1"] - d["boom_y0"]
    out.extend(box_tube("04 Reach Boom", "boom",
                        (0, (d["boom_y0"] + d["boom_y1"]) / 2.0, beam_z),
                        (d["beam_w"], d["beam_h"]), boom_len, "y", d["wall"]))

    # -- 05 Main crossbeam ------------------------------------------------
    out.extend(box_tube("05 Main Crossbeam", "crossbeam",
                        (0, d["beam_y"], beam_z),
                        (d["beam_w"], d["beam_h"]), d["beam_len"], "x", d["wall"]))

    # -- 06 Telescoping arms, sized to slide inside the beam --------------
    arm_sy = d["beam_w"] - 2 * d["wall"] - 4
    arm_sz = d["beam_h"] - 2 * d["wall"] - 4
    for side, tag in ((-1, "L"), (1, "R")):
        arm_cx = side * (half_beam - d["arm_len"] / 2.0 + d["arm_ext"])
        out.append(box("06 Telescoping Arms", "arm_%s" % tag,
                       (arm_cx, d["beam_y"], beam_z),
                       (d["arm_len"], arm_sy, arm_sz)))

    # -- 07 Tire cradles: the only part that touches the vehicle ----------
    roller_r = d["roller_dia"] / 2.0
    roller_cz = d["road_gap"] + roller_r
    cradle_cy = d["beam_y"] + 220.0
    plate_dx = d["roller_len"] / 2.0 + 6.0

    for side, tag in ((-1, "L"), (1, "R")):
        cx = side * (d["track"] / 2.0)

        out.append(box("07 Tire Cradles", "bracket_%s" % tag,
                       (cx, d["beam_y"] + 20, beam_z),
                       (d["roller_len"] + 24, 40, arm_sz)))

        for sign, pos in ((-1, "aft"), (1, "fwd")):
            out.append(cyl_x("07 Tire Cradles", "roller_%s_%s" % (tag, pos),
                             (cx, cradle_cy + sign * d["roller_gap"] / 2.0, roller_cz),
                             d["roller_dia"], d["roller_len"]))

        for sign, pos in ((-1, "in"), (1, "out")):
            out.append(box("07 Tire Cradles", "plate_%s_%s" % (tag, pos),
                           (cx + sign * plate_dx, cradle_cy, 85),
                           (12, d["roller_gap"] + d["roller_dia"] + 60, 130)))

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
    ]
