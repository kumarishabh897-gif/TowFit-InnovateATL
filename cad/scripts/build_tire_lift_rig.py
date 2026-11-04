"""
ClearanceOS "tire-lift mover v1" - Fusion 360 model builder.

Run from Fusion: Utilities > ADD-INS > Scripts and Add-Ins > Scripts > Run.

The geometry itself lives in rig_spec.py, which is plain Python and knows
nothing about Fusion. This file only turns that part list into solids. Keeping
the split means the STL exporter and any test see exactly the same rig as
Fusion does.

Concept model for the pitch. Not a design for fabrication: nothing here has
been through a stress case, and every envelope number it respects is still
PLACEHOLDER in config/assumptions.yaml.

Author: VK12034
"""

import math
import os
import sys
import traceback

import adsk.core
import adsk.fusion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_spec  # noqa: E402


def cm(mm_value):
    """Fusion's API is centimetres; the design is millimetres."""
    return mm_value / 10.0


def _plane_at_z(comp, z_mm):
    """Construction plane parallel to XY at height z.

    Offsetting from XY is the one direction whose normal sign is not in doubt
    (+Z), which is why every solid is built as a Z-extrusion and rotated into
    place afterwards if it needs to lie down.
    """
    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(cm(z_mm))
    )
    return planes.add(plane_input)


def _extrude_symmetric(comp, profile, length_mm, name):
    """Symmetric extent: the plane's normal direction cannot matter, which
    removes a whole class of silent mirror-image bugs."""
    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_input.setSymmetricExtent(
        adsk.core.ValueInput.createByReal(cm(length_mm)), True
    )
    body = extrudes.add(ext_input).bodies.item(0)
    body.name = name
    return body


def make_box(comp, part):
    cx, cy, cz = part["centre"]
    sx, sy, sz = part["size"]
    sketch = comp.sketches.add(_plane_at_z(comp, cz))
    p0 = adsk.core.Point3D.create(cm(cx - sx / 2), cm(cy - sy / 2), 0)
    p1 = adsk.core.Point3D.create(cm(cx + sx / 2), cm(cy + sy / 2), 0)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(p0, p1)
    return _extrude_symmetric(comp, sketch.profiles.item(0), sz, part["name"])


def make_cyl_x(comp, part):
    """Cylinder along X: built along Z, then rotated 90 degrees about Y
    through its own centre - a transform we control completely, rather than
    trusting the sign of the YZ plane's normal."""
    cx, cy, cz = part["centre"]
    sketch = comp.sketches.add(_plane_at_z(comp, cz))
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cm(cx), cm(cy), 0), cm(part["diameter"]) / 2.0
    )
    body = _extrude_symmetric(comp, sketch.profiles.item(0), part["length"], part["name"])

    rotation = adsk.core.Matrix3D.create()
    rotation.setToRotation(
        math.pi / 2.0,
        adsk.core.Vector3D.create(0, 1, 0),
        adsk.core.Point3D.create(cm(cx), cm(cy), cm(cz)),
    )
    targets = adsk.core.ObjectCollection.create()
    targets.add(body)
    move_input = comp.features.moveFeatures.createInput2(targets)
    move_input.defineAsFreeMove(rotation)
    comp.features.moveFeatures.add(move_input)
    return body


def add_parameters(design, derived):
    """Expose the envelope in Fusion's parameter table.

    Documentation inside the model: an engineer who opens the .f3d sees the
    same numbers the rule engine checks against, each with the registry key
    it came from and its status.
    """
    unit = rig_spec.UNIT
    rows = [
        ("rig_capacity_lb", derived["capacity_lb"], "",
         "unit.%s.rig_capacity_lb - PLACEHOLDER" % unit),
        ("rig_tire_width_min", derived["tire_min"], "mm",
         "unit.%s.rig_tire_width_range_mm[0] - PLACEHOLDER" % unit),
        ("rig_tire_width_max", derived["tire_max"], "mm",
         "unit.%s.rig_tire_width_range_mm[1] - PLACEHOLDER" % unit),
        ("rig_min_ground_clearance", derived["min_clearance"], "mm",
         "unit.%s.rig_min_ground_clearance_mm - PLACEHOLDER" % unit),
        ("rig_max_wheelbase", derived["max_wheelbase"], "mm",
         "unit.%s.rig_max_wheelbase_mm - PLACEHOLDER" % unit),
        ("beam_height", derived["beam_h"], "mm",
         "derived: clearance - road gap - safety"),
        ("roller_length", derived["roller_len"], "mm",
         "derived: widest tire + 45 mm margin"),
        ("road_gap", derived["road_gap"], "mm", "concept estimate, not sourced"),
        ("lift_stroke", derived["lift_stroke"], "mm", "concept estimate, not sourced"),
        ("assumed_axle_track", derived["track"], "mm", "concept estimate, not sourced"),
    ]
    for name, value, units, comment in rows:
        try:
            design.userParameters.add(
                name,
                adsk.core.ValueInput.createByReal(cm(value) if units == "mm" else value),
                units,
                comment,
            )
        except Exception:
            pass  # a name collision on re-run is not worth aborting the build


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        envelope, source = rig_spec.load_envelope()
        derived = rig_spec.derive(envelope)
        part_list = rig_spec.parts(envelope)

        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.unitsManager.distanceDisplayUnits = (
            adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        )

        root = design.rootComponent
        root.name = "ClearanceOS tire-lift mover v1"

        components = {}
        for part in part_list:
            key = part["component"]
            if key not in components:
                occurrence = root.occurrences.addNewComponent(
                    adsk.core.Matrix3D.create()
                )
                occurrence.component.name = key
                components[key] = occurrence.component
            comp = components[key]

            if part["kind"] == "box":
                make_box(comp, part)
            elif part["kind"] == "cyl_x":
                make_cyl_x(comp, part)
            else:
                raise ValueError("unknown primitive %r" % part["kind"])

        add_parameters(design, derived)
        app.activeViewport.fit()

        failures = [c for c in rig_spec.checks(envelope) if not c[1]]
        verdict = (
            "all %d envelope checks pass" % len(rig_spec.checks(envelope))
            if not failures
            else "FAILED: " + "; ".join(f[0] for f in failures)
        )

        ui.messageBox(
            "ClearanceOS tire-lift mover v1 built.\n\n"
            "%d bodies across %d components.\n\n"
            "Envelope source:\n%s\n\n"
            "capacity           %d lb\n"
            "tire width         %d - %d mm\n"
            "min ground clear   %d mm  ->  %d mm beam + %d mm road gap\n"
            "max wheelbase      %d mm\n\n"
            "%s\n\n"
            "Every envelope value above is PLACEHOLDER in the registry.\n"
            "Concept model for the pitch, not a design for fabrication."
            % (
                len(part_list), len(components), source,
                derived["capacity_lb"],
                derived["tire_min"], derived["tire_max"],
                derived["min_clearance"], derived["beam_h"], derived["road_gap"],
                derived["max_wheelbase"],
                verdict,
            ),
            "TowFit CAD",
        )

    except Exception:
        if ui:
            ui.messageBox("Build failed:\n%s" % traceback.format_exc(), "TowFit CAD")
