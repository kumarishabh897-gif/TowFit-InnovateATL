"""
ClearanceOS "tire-lift mover v1" - Fusion 360 model builder.

Run from Fusion: Utilities > ADD-INS > Scripts and Add-Ins > Scripts > Run.

The geometry lives in rig_spec.py, which is plain Python and knows nothing
about Fusion. This file only turns that part list into solids, so the STL
exporter, the drawings and Fusion all describe the same rig.

Concept model for the pitch. Not a design for fabrication: nothing here has
been through a stress case, and every envelope number it respects is still
PLACEHOLDER in config/assumptions.yaml.

Author: VK12034
"""

import importlib
import math
import os
import sys
import traceback

import adsk.core
import adsk.fusion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_spec  # noqa: E402

# Fusion keeps one Python interpreter alive for the whole session, so an
# already-imported rig_spec stays cached in sys.modules and edits to it are
# invisible to later runs - the script silently builds the previous geometry.
# Reloading on every run is the difference between editing the spec and
# wondering why nothing changed.
importlib.reload(rig_spec)

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

# Set to True by a caller that has no one to click OK - running through the
# Fusion MCP connector, say, where a modal dialog would hang the session.
# The summary is printed either way.
QUIET = False


def cm(mm_value):
    """Fusion's API is centimetres; the design is millimetres."""
    return mm_value / 10.0


_PLANE_CACHE = {}


def _plane(comp, axis, coord_mm):
    """Construction plane perpendicular to `axis` at `coord_mm`.

    Fusion's XZ and YZ planes do not have a documented normal sign, so an
    offset can land on the wrong side. Rather than hard-code an assumption,
    place the plane, read back where it actually went, and flip if needed.

    Planes are cached per component and position. The rig has 163 parts but
    far fewer distinct planes - most of the crossbeam, boom and arm hardware
    sits at the same few heights - and construction planes are among the more
    expensive things to create in bulk.
    """
    key = (comp.entityToken, axis, round(coord_mm, 4))
    cached = _PLANE_CACHE.get(key)
    if cached is not None:
        return cached

    base = {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }[axis]
    idx = _AXIS_INDEX[axis]
    want = cm(coord_mm)
    planes = comp.constructionPlanes

    for distance in (want, -want):
        plane_input = planes.createInput()
        plane_input.setByOffset(base, adsk.core.ValueInput.createByReal(distance))
        plane = planes.add(plane_input)
        if abs(plane.geometry.origin.asArray()[idx] - want) < 1e-6:
            _PLANE_CACHE[key] = plane
            return plane
        plane.deleteMe()
    raise RuntimeError("could not place a %s plane at %.3f mm" % (axis, coord_mm))


def _sketch_point(sketch, world_mm):
    """World mm -> this sketch's own 2D space.

    Letting Fusion do the conversion means the sketch's axis mapping never has
    to be guessed; it works the same on every plane.
    """
    point = adsk.core.Point3D.create(
        cm(world_mm[0]), cm(world_mm[1]), cm(world_mm[2])
    )
    return sketch.modelToSketchSpace(point)


def _extrude(comp, profile, length_mm, name):
    """Symmetric extent, so the plane's normal direction cannot matter."""
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


def _ring_profile(sketch):
    """The profile bounded by two loops - the wall of a hollow section."""
    for i in range(sketch.profiles.count):
        profile = sketch.profiles.item(i)
        if profile.profileLoops.count == 2:
            return profile
    return sketch.profiles.item(0)


def _apply_rotation(comp, body, rot):
    if not rot:
        return
    axis_vector = {
        "x": adsk.core.Vector3D.create(1, 0, 0),
        "y": adsk.core.Vector3D.create(0, 1, 0),
        "z": adsk.core.Vector3D.create(0, 0, 1),
    }[rot["axis"]]
    pivot = adsk.core.Point3D.create(
        cm(rot["pivot"][0]), cm(rot["pivot"][1]), cm(rot["pivot"][2])
    )
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(math.radians(rot["deg"]), axis_vector, pivot)

    targets = adsk.core.ObjectCollection.create()
    targets.add(body)
    move_input = comp.features.moveFeatures.createInput2(targets)
    move_input.defineAsFreeMove(matrix)
    comp.features.moveFeatures.add(move_input)


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def make_box(comp, part):
    cx, cy, cz = part["centre"]
    sx, sy, sz = part["size"]
    sketch = comp.sketches.add(_plane(comp, "z", cz))
    p0 = _sketch_point(sketch, (cx - sx / 2, cy - sy / 2, cz))
    p1 = _sketch_point(sketch, (cx + sx / 2, cy + sy / 2, cz))
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(p0, p1)
    return _extrude(comp, sketch.profiles.item(0), sz, part["name"])


def make_cyl(comp, part):
    axis = part["axis"]
    centre = part["centre"]
    sketch = comp.sketches.add(_plane(comp, axis, centre[_AXIS_INDEX[axis]]))
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        _sketch_point(sketch, centre), cm(part["diameter"]) / 2.0
    )
    return _extrude(comp, sketch.profiles.item(0), part["length"], part["name"])


def make_tube_cyl(comp, part):
    axis = part["axis"]
    centre = part["centre"]
    sketch = comp.sketches.add(_plane(comp, axis, centre[_AXIS_INDEX[axis]]))
    origin = _sketch_point(sketch, centre)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(origin, cm(part["od"]) / 2.0)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(origin, cm(part["idia"]) / 2.0)
    return _extrude(comp, _ring_profile(sketch), part["length"], part["name"])


def make_gusset(comp, part):
    """Right-triangle prism in a named plane."""
    plane_name = part["plane"]
    axis = {"yz": "x", "xz": "y", "xy": "z"}[plane_name]
    at = part["at"]
    u0, v0 = part["corner"]
    du, dv = part["legs"]

    def world(u, v):
        if plane_name == "yz":
            return (at, u, v)
        if plane_name == "xz":
            return (u, at, v)
        return (u, v, at)

    sketch = comp.sketches.add(_plane(comp, axis, at))
    corners = [world(u0, v0), world(u0 + du, v0), world(u0, v0 + dv)]
    pts = [_sketch_point(sketch, c) for c in corners]
    lines = sketch.sketchCurves.sketchLines
    lines.addByTwoPoints(pts[0], pts[1])
    lines.addByTwoPoints(pts[1], pts[2])
    lines.addByTwoPoints(pts[2], pts[0])
    return _extrude(comp, sketch.profiles.item(0), part["thickness"], part["name"])


BUILDERS = {
    "box": make_box,
    "cyl": make_cyl,
    "tube_cyl": make_tube_cyl,
    "gusset": make_gusset,
}


# --------------------------------------------------------------------------
# Document, parameters, appearances
# --------------------------------------------------------------------------

def _new_design(app):
    """Always create a fresh document for this build, and return it directly.

    This deliberately never reuses an existing document. An earlier version
    reused one that was unsaved, unnamed and empty, which is exactly the shape
    of another Claude session's scratch document in the same Fusion process -
    and since this script switches the design to direct modelling, reusing one
    would discard that session's timeline and fill its document with this rig.
    One Fusion process can have several drivers; "looks empty" is not consent.

    The stranded-document problem that reuse was solving is handled at the
    other end instead: run() closes this document if the build fails before
    producing anything.

    Returning the document's own Design rather than reading app.activeProduct
    matters for the same reason. Another session can change the active
    document between any two calls, and every later lookup would then land in
    their file.
    """
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        # Scan the products and cast, rather than asking for one by name.
        # The identifier is "DesignProductType", not "Design", and
        # itemByProductType raises rather than returning None when it misses -
        # so a guess at the string orphans the document it just created.
        design = None
        for i in range(doc.products.count):
            candidate = adsk.fusion.Design.cast(doc.products.item(i))
            if candidate is not None:
                design = candidate
                break
        if design is None:
            raise RuntimeError("newly created document has no Design product")
        return doc, design
    except Exception:
        # Never leave behind a document this function created.
        try:
            doc.close(False)
        except Exception:
            pass
        raise


def add_parameters(design, derived):
    """Expose the envelope in Fusion's parameter table.

    Documentation inside the model: an engineer who opens the .f3d sees the
    same numbers the rule engine checks against, each with the registry key it
    came from and its status.
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
        ("lift_arm_length", derived["arm_run"], "mm", "derived: pivot to knee"),
        ("lift_arm_angle", derived["arm_deg"], "deg", "derived: arm rake, lowered"),
        ("ram_closed_length", derived["ram_run"], "mm", "derived: anchor to lug"),
        ("road_gap", derived["road_gap"], "mm", "concept estimate, not sourced"),
        ("lift_stroke", derived["lift_stroke"], "mm", "concept estimate, not sourced"),
        ("assumed_axle_track", derived["track"], "mm", "concept estimate, not sourced"),
    ]
    for name, value, units, comment in rows:
        try:
            if units == "mm":
                value_input = adsk.core.ValueInput.createByReal(cm(value))
            elif units == "deg":
                value_input = adsk.core.ValueInput.createByReal(math.radians(value))
            else:
                value_input = adsk.core.ValueInput.createByReal(value)
            design.userParameters.add(name, value_input, units, comment)
        except Exception:
            pass  # a name collision on re-run is not worth aborting the build


def apply_appearances(app, design, components):
    """Give each component a material so the model reads as equipment.

    Entirely cosmetic, and the appearance library names vary between Fusion
    releases, so every step is optional.
    """
    applied, missing = 0, []
    try:
        library = app.materialLibraries.itemByName("Fusion Appearance Library")
        if library is None:
            return 0, ["no Fusion Appearance Library"]
    except Exception as exc:
        return 0, ["appearance library unavailable: %s" % exc]

    # addByCopy fails once an appearance of that name is already in the
    # document, so several components asking for the same material would
    # silently lose all but the first. Copy once, then reuse.
    local = {}

    def resolve(wanted):
        if wanted in local:
            return local[wanted]
        existing = design.appearances.itemByName(wanted)
        if existing is None:
            source = library.appearances.itemByName(wanted)
            if source is None:
                local[wanted] = None
                return None
            existing = design.appearances.addByCopy(source, wanted)
        local[wanted] = existing
        return existing

    for name, comp in components.items():
        wanted = rig_spec.MATERIALS.get(name)
        if not wanted:
            continue
        try:
            appearance = resolve(wanted)
            if appearance is None:
                missing.append("%s: no appearance named %r" % (name, wanted))
                continue
            for i in range(comp.bRepBodies.count):
                comp.bRepBodies.item(i).appearance = appearance
            applied += 1
        except Exception as exc:
            missing.append("%s: %s" % (name, exc))
    return applied, missing


def export_outputs(design):
    """Write .f3d and .step straight into the repo's cad/exports.

    Doing this from the script rather than File > Export means the outputs
    land next to the STL and drawings automatically, with no dialog to fill
    in and no chance of them going to Downloads instead.
    """
    out_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exports")
    )
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        return ["could not create %s: %s" % (out_dir, exc)]

    manager = design.exportManager
    written = []
    for label, suffix, factory in (
        ("Fusion archive", ".f3d", "createFusionArchiveExportOptions"),
        ("STEP", ".step", "createSTEPExportOptions"),
    ):
        path = os.path.join(out_dir, "tire_lift_mover_v1" + suffix)
        try:
            options = getattr(manager, factory)(path)
            manager.execute(options)
            size = os.path.getsize(path) / 1024.0 if os.path.isfile(path) else 0.0
            written.append("%s -> %s (%.0f KB)" % (label, os.path.basename(path), size))
        except Exception as exc:
            written.append("%s FAILED: %s" % (label, exc))
    return written


def run(context):
    ui = None
    doc = None
    design = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        envelope, source = rig_spec.load_envelope()
        derived = rig_spec.derive(envelope)
        part_list = rig_spec.parts(envelope)

        doc, design = _new_design(app)
        # Direct modelling, not parametric. The parametric model IS
        # rig_spec.py - nobody will ever hand-edit the generated timeline -
        # and a 163-part build creates enough history to make Fusion crawl or
        # fall over. Dropping the timeline keeps the build light.
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        design.unitsManager.distanceDisplayUnits = (
            adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        )
        _PLANE_CACHE.clear()
        root = design.rootComponent
        try:
            root.name = "ClearanceOS tire-lift mover v1"
        except RuntimeError:
            # Fusion ties the root component's name to the document and
            # refuses to set it on an unsaved document. Not worth failing over.
            pass

        components = {}
        failures = []
        for part in part_list:
            key = part["component"]
            if key not in components:
                occurrence = root.occurrences.addNewComponent(
                    adsk.core.Matrix3D.create()
                )
                occurrence.component.name = key
                components[key] = occurrence.component
            comp = components[key]

            builder = BUILDERS.get(part["kind"])
            if builder is None:
                raise ValueError("unknown primitive %r" % part["kind"])
            try:
                body = builder(comp, part)
                _apply_rotation(comp, body, part.get("rot"))
            except Exception as exc:
                failures.append("%s/%s: %s" % (key, part["name"], exc))

        add_parameters(design, derived)
        styled, unstyled = apply_appearances(app, design, components)
        failures.extend(unstyled)
        # Fit only while our own document is still in front. Another session
        # sharing this Fusion process may have switched away, and zooming
        # someone else's view mid-task is both confusing and not ours to do.
        try:
            if app.activeDocument is doc:
                app.activeViewport.fit()
        except Exception:
            pass
        exported = export_outputs(design)

        results = rig_spec.checks(envelope)
        bad = [c for c in results if not c[1]]
        verdict = ("all %d checks pass" % len(results) if not bad
                   else "FAILED: " + "; ".join(c[0] for c in bad))

        note = "\n\nexports:\n  " + "\n  ".join(exported)
        if failures:
            note += "\n\n%d part(s) failed to build:\n%s" % (
                len(failures), "\n".join(failures[:6])
            )

        # Printed as well as shown: when this runs through the MCP connector
        # rather than the Scripts dialog, nobody is there to click OK.
        print("built %d parts across %d components, %d styled"
              % (len(part_list) - len(failures), len(components), styled))
        for line in exported:
            print("  " + line)
        for line in failures[:10]:
            print("  FAILED " + line)

        if QUIET:
            return

        ui.messageBox(
            "ClearanceOS tire-lift mover v1 built.\n\n"
            "%d parts across %d components, %d styled.\n\n"
            "Envelope source:\n%s\n\n"
            "capacity           %d lb\n"
            "tire width         %d - %d mm\n"
            "min ground clear   %d mm  ->  %d mm beam + %d mm road gap\n"
            "max wheelbase      %d mm\n\n"
            "lift arm           %.0f mm at %.1f deg\n"
            "ram closed         %.0f mm at %.1f deg\n\n"
            "%s%s\n\n"
            "Every envelope value above is PLACEHOLDER in the registry.\n"
            "Concept model for the pitch, not a design for fabrication."
            % (
                len(part_list) - len(failures), len(components), styled, source,
                derived["capacity_lb"], derived["tire_min"], derived["tire_max"],
                derived["min_clearance"], derived["beam_h"], derived["road_gap"],
                derived["max_wheelbase"],
                derived["arm_run"], derived["arm_deg"],
                derived["ram_run"], derived["ram_deg"],
                verdict, note,
            ),
            "TowFit CAD",
        )

    except Exception:
        detail = traceback.format_exc()
        print("BUILD FAILED\n" + detail)

        # Clean up our own document rather than leaving an empty tab behind.
        # Only when it is still empty: once there is geometry, leaving it open
        # is worth more for diagnosis than a tidy tab list. Never touches any
        # other document, which is the whole point of creating our own.
        if doc is not None and design is not None:
            try:
                root = design.rootComponent
                if root.occurrences.count == 0 and root.bRepBodies.count == 0:
                    doc.close(False)
                    print("closed the empty document this run created")
            except Exception:
                pass

        if ui and not QUIET:
            ui.messageBox("Build failed:\n%s" % detail, "TowFit CAD")
        raise
