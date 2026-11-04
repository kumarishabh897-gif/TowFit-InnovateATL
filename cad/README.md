# CAD — ClearanceOS tire-lift mover v1

The rig TowFit is reasoning about. It mounts on a patrol car's rear hitch
receiver, reaches under a disabled vehicle, grips one axle's tires between
paired rollers, lifts them clear of the road, and lets the patrol car draw the
vehicle — in neutral — out of a live lane.

> **Concept model for the pitch. Not a design for fabrication.**
> Nothing here has been through a load case. Every envelope value it respects
> is still `PLACEHOLDER` in `config/assumptions.yaml`.

![Three orthographic views of the rig](reference/rig_views.svg)

## Why the model is a script, not a checked-in part file

The rig envelope lives in `config/assumptions.yaml` because the rule engine
checks real vehicles against it — `R-DIM-TIRE-WIDTH`, `R-DIM-CLEARANCE`,
`R-DIM-WHEELBASE` in `services/api/app/engine/towfit.py` all read those keys.

If the CAD carried its own copy of those numbers, the two would drift the
first time the hardware team supplied a real one, and nobody would notice
until a `RED` verdict disagreed with a part that physically fits. So the
geometry is **derived from that file at build time**. Change the registry,
re-run, and the solid is correct by construction.

```
config/assumptions.yaml ──► cad/scripts/rig_spec.py ──┬──► build_tire_lift_rig.py  (Fusion 360)
                                                      ├──► export_stl.py           (.stl)
                                                      └──► export_views.py         (.svg)
```

`rig_spec.py` is the only place the geometry exists. If a consumer ever
disagrees with it, the consumer is wrong.

## Files

| Path | What |
|---|---|
| `scripts/rig_spec.py` | Geometry + envelope loading. Pure Python, no dependencies. |
| `scripts/build_tire_lift_rig.py` | Fusion 360 script. Builds the parametric solid. |
| `scripts/export_stl.py` | Writes a binary STL. No Fusion, no packages. |
| `scripts/export_views.py` | Writes the three-view SVG above. |
| `exports/` | Build outputs. Regenerate rather than hand-edit. |
| `reference/` | Generated drawings. |

## Rebuild

```bash
python cad/scripts/export_stl.py     # .stl + envelope checks
python cad/scripts/export_views.py   # .svg
```

Both print which file the envelope came from, and `export_stl.py` exits
non-zero if the geometry violates it.

In Fusion 360: **Utilities → ADD-INS → Scripts and Add-Ins → Scripts**, add
`cad/scripts/`, run `build_tire_lift_rig`. It builds into a new document,
writes the envelope into the parameter table with each value's registry key,
and reports pass/fail on the same checks.

## How it works

The vehicle must be in neutral — that is the rule engine's central
precondition, and it is what makes a one-axle lift sufficient. The lifted
axle's tires come off the road; the other axle rolls.

1. **Stinger** into a 2 in Class III receiver at 400 mm.
2. **Mast** carries the lift carriage, 150 mm of stroke.
3. **Reach boom** takes the beam 560 mm forward, under the vehicle.
4. **Crossbeam**, 60 mm tall box section, spans the axle.
5. **Telescoping arms** extend to ±950 mm to meet the track.
6. **Tire cradles** — two Ø90 mm rollers, 220 mm apart, per wheel. The tire
   settles between them; raising the carriage lifts it.

## Where the numbers come from

**From the registry** (`unit.patrol_42.*`, all `PLACEHOLDER`):

| Envelope | Value | Drives |
|---|---|---|
| `rig_capacity_lb` | 6 000 lb | Nothing geometric yet — recorded in the parameter table |
| `rig_tire_width_range_mm` | 155–315 mm | Roller length = 315 + 45 = **360 mm** |
| `rig_min_ground_clearance_mm` | 90 mm | Beam height = 90 − 20 road gap − 10 safety = **60 mm** |
| `rig_max_wheelbase_mm` | 4 000 mm | Recorded; the rig grips one axle, so wheelbase bounds approach, not section |

**Not from the registry — concept estimates, unsourced and unanalysed:**
wall thickness (6 mm), beam depth (100 mm), beam length (1 400 mm), road gap
(20 mm), roller diameter (90 mm), roller spacing (220 mm), hitch height
(400 mm), mast height (460 mm), lift stroke (150 mm), assumed axle track
(1 550 mm).

The assumed track is the one worth arguing with: it is a guess at a typical
passenger-car axle, and the arms are sized from it rather than from anything
measured.

## Envelope checks

`export_stl.py` asserts the geometry against the envelope and fails loudly:

```
[PASS] beam fits under min ground clearance             80 mm beam top vs 90 mm clearance
[PASS] rollers span the widest gripped tire             360 mm roller vs 315 mm tire
[PASS] rollers still support the narrowest gripped tire 360 mm roller vs 155 mm tire
[PASS] beam spans a typical axle track                  1900 mm extended vs 1550 mm track
[PASS] arms clear the beam's internal section           44 mm arm height
```

The first is the one that matters. `rig_min_ground_clearance_mm` is the
promise that the rig can reach under a vehicle; the beam is the part that has
to keep it. At 90 mm clearance the beam is 60 mm with a 20 mm road gap,
leaving 10 mm. **Lower that assumption and the beam has to get thinner** — at
roughly 40 mm of clearance the section stops being buildable in steel, which
is a hardware answer, not a CAD one.

## What this model does not do

- **No stress analysis.** 6 000 lb is in the parameter table as a number, not
  a load case. Section sizes are drawn for proportion.
- **No joints or motion study.** Built in the lowered position. The 150 mm
  stroke is a dimension, not a constrained mechanism.
- **No patrol car.** The receiver interface is modelled; the vehicle is not.
- **Overlapping solids at joints**, not welds or fasteners.
- **No hydraulics.** The actuator is a stand-in block.

## Open questions for the hardware team

1. Real `rig_capacity_lb`, and is the limit the rig or the patrol car?
2. Real tire-width grip range — 155–315 mm is invented.
3. Real minimum ground clearance. This one sets the beam section.
4. Axle track range to size arm extension against.
5. Is a hitch receiver the actual mount, or is it chassis-mounted?

Answers belong in `config/assumptions.yaml` with status moved off
`PLACEHOLDER`. Re-running the scripts then updates the model.
