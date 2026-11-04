"""
Render the rig as three orthographic views in a single SVG.

    python cad/scripts/export_views.py [output.svg]

An STL needs a viewer and the .f3d needs Fusion. This produces something that
renders in a browser, in a pull request, and in the pitch deck, straight from
the same rig_spec.py the solids come from - so a reviewer can check the rig's
proportions without installing anything.

Silhouettes only: each part is drawn as its bounding rectangle in each view
(a roller shows as a circle in the side view). It is a proportion check and a
communication aid, not a dimensioned engineering drawing.

Author: VK12034
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_spec  # noqa: E402

# One colour per component so the views read as an assembly, not a blob.
COLOURS = {
    "01 Receiver Stinger": "#8b93a7",
    "02 Mast": "#6f7b92",
    "03 Lift Actuator": "#c2703d",
    "04 Reach Boom": "#4e7ca1",
    "05 Main Crossbeam": "#3f6c93",
    "06 Telescoping Arms": "#5c9ec7",
    "07 Tire Cradles": "#c9a227",
}


def silhouettes(part, view):
    """Return drawables for a part in a given view.

    ('rect', x, y, w, h) or ('circle', cx, cy, r), in millimetres, in that
    view's own 2D frame.
    """
    cx, cy, cz = part["centre"]

    if part["kind"] == "box":
        sx, sy, sz = part["size"]
        if view == "top":
            return [("rect", cx - sx / 2, cy - sy / 2, sx, sy)]
        if view == "front":
            return [("rect", cx - sx / 2, cz - sz / 2, sx, sz)]
        return [("rect", cy - sy / 2, cz - sz / 2, sy, sz)]

    d, length = part["diameter"], part["length"]
    if view == "top":
        return [("rect", cx - length / 2, cy - d / 2, length, d)]
    if view == "front":
        return [("rect", cx - length / 2, cz - d / 2, length, d)]
    return [("circle", cy, cz, d / 2)]


VIEWS = [
    ("top", "TOP  (looking down)", "X lateral", "Y fore-aft"),
    ("front", "FRONT  (from the disabled vehicle)", "X lateral", "Z height"),
    ("side", "SIDE  (from the kerb)", "Y fore-aft", "Z height"),
]


def view_bounds(part_list, view):
    xs, ys = [], []
    for part in part_list:
        for shape in silhouettes(part, view):
            if shape[0] == "rect":
                _, x, y, w, h = shape
                xs += [x, x + w]
                ys += [y, y + h]
            else:
                _, ox, oy, r = shape
                xs += [ox - r, ox + r]
                ys += [oy - r, oy + r]
    return min(xs), max(xs), min(ys), max(ys)


def render(part_list, derived, out_path):
    scale = 0.22           # mm -> px
    pad = 46
    gap = 34
    panels, total_h, max_w = [], 0, 0

    for view, title, xlabel, ylabel in VIEWS:
        x0, x1, y0, y1 = view_bounds(part_list, view)
        w = (x1 - x0) * scale
        h = (y1 - y0) * scale
        panels.append((view, title, xlabel, ylabel, x0, x1, y0, y1, w, h))
        total_h += h + gap + 30
        max_w = max(max_w, w)

    width = max_w + pad * 2
    height = total_h + pad * 2

    out = []
    out.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" '
        'viewBox="0 0 %.0f %.0f" font-family="ui-sans-serif, system-ui, sans-serif">'
        % (width, height, width, height)
    )
    out.append('<rect width="100%" height="100%" fill="#0f1319"/>')
    out.append(
        '<text x="%.0f" y="30" fill="#e8ecf2" font-size="17" font-weight="600">'
        "ClearanceOS tire-lift mover v1</text>" % pad
    )
    out.append(
        '<text x="%.0f" y="48" fill="#7f8b9e" font-size="11">'
        "concept model - all envelope values PLACEHOLDER in config/assumptions.yaml"
        "</text>" % pad
    )

    cursor_y = pad + 34
    for view, title, xlabel, ylabel, x0, x1, y0, y1, w, h in panels:
        out.append(
            '<text x="%.0f" y="%.0f" fill="#9fb0c7" font-size="12" '
            'font-weight="600">%s</text>' % (pad, cursor_y, title)
        )
        out.append(
            '<text x="%.0f" y="%.0f" fill="#5d6a7d" font-size="10">'
            "%s horizontal, %s vertical</text>"
            % (pad + 260, cursor_y, xlabel, ylabel)
        )
        top = cursor_y + 12

        # Ground line on the elevation views, where Z is vertical.
        if view in ("front", "side"):
            gy = top + (y1 - 0.0) * scale
            out.append(
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                'stroke="#3a4454" stroke-width="1.5" stroke-dasharray="6 4"/>'
                % (pad - 10, gy, pad + w + 10, gy)
            )
            out.append(
                '<text x="%.1f" y="%.1f" fill="#4f5b6d" font-size="9">road</text>'
                % (pad + w + 14, gy + 3)
            )

        for part in part_list:
            colour = COLOURS.get(part["component"], "#8899aa")
            for shape in silhouettes(part, view):
                if shape[0] == "rect":
                    _, rx, ry, rw, rh = shape
                    px = pad + (rx - x0) * scale
                    py = top + (y1 - (ry + rh)) * scale
                    out.append(
                        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                        'fill="%s" fill-opacity="0.68" stroke="%s" '
                        'stroke-width="0.7"/>'
                        % (px, py, rw * scale, rh * scale, colour, colour)
                    )
                else:
                    _, ox, oy, r = shape
                    px = pad + (ox - x0) * scale
                    py = top + (y1 - oy) * scale
                    out.append(
                        '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" '
                        'fill-opacity="0.68" stroke="%s" stroke-width="0.7"/>'
                        % (px, py, r * scale, colour, colour)
                    )

        out.append(
            '<text x="%.0f" y="%.1f" fill="#4f5b6d" font-size="9">'
            "%.0f x %.0f mm</text>" % (pad, top + h + 13, x1 - x0, y1 - y0)
        )
        cursor_y = top + h + gap + 12

    # Legend
    lx, ly = pad, height - 16
    for i, (name, colour) in enumerate(sorted(COLOURS.items())):
        ox = lx + (i % 4) * 215
        oy = ly - (24 if i < 4 else 0)
        out.append(
            '<rect x="%.0f" y="%.0f" width="9" height="9" fill="%s"/>'
            % (ox, oy - 8, colour)
        )
        out.append(
            '<text x="%.0f" y="%.0f" fill="#7f8b9e" font-size="9.5">%s</text>'
            % (ox + 14, oy, name)
        )

    out.append("</svg>")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))
    return out_path


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.normpath(
        os.path.join(here, "..", "reference", "rig_views.svg")
    )
    out_path = argv[1] if len(argv) > 1 else default

    envelope, source = rig_spec.load_envelope()
    part_list = rig_spec.parts(envelope)
    derived = rig_spec.derive(envelope)

    render(part_list, derived, out_path)
    print("envelope source : %s" % source)
    print("written         : %s (%.1f KB)"
          % (out_path, os.path.getsize(out_path) / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
