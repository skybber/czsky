"""User drawings (polylines, polygons, points) overlaid on charts.

Drawings are created in the browser (sky_scene_drawings.js) and sent to the server
only when a server-side chart is rendered (PDF / PNG). Two transport formats exist:

* JSON (POST form field ``drawings``)::

    {"version": 1, "items": [{"type": "polyline", "coords": [[ra, dec], ...], "label": "..."}]}

  ra/dec are J2000 radians.

* compact (query parameter ``drw``), used in shareable URLs and GET image requests::

    L83.6331_22.0145_84.1_21.2*P...*T83.1_22.0~Start

  Items are separated by ``*``. Each item is a type letter (L=polyline, P=polygon,
  T=point) followed by ra/dec pairs in degrees separated by ``_`` and an optional
  ``~``-prefixed percent-encoded label.
"""
import json
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import unquote

from flask import request
from fchart3.graphics import DrawMode
from fchart3.renderers import TrajectoryRenderer

DRAWINGS_FORM_FIELD = 'drawings'
DRAWINGS_QUERY_PARAM = 'drw'

DRAWING_COLOR = (0.95, 0.15, 0.15)

MAX_ITEMS = 200
MAX_TOTAL_VERTICES = 5000
MAX_LABEL_LEN = 64
MAX_PAYLOAD_LEN = 512 * 1024

TYPE_POLYLINE = 'polyline'
TYPE_POLYGON = 'polygon'
TYPE_POINT = 'point'

_MIN_VERTICES = {
    TYPE_POLYLINE: 2,
    TYPE_POLYGON: 3,
    TYPE_POINT: 1,
}

_COMPACT_TYPES = {
    'L': TYPE_POLYLINE,
    'P': TYPE_POLYGON,
    'T': TYPE_POINT,
}


@dataclass
class ChartDrawing:
    kind: str
    coords: List[Tuple[float, float]] = field(default_factory=list)
    label: Optional[str] = None


def _normalize_label(label):
    if label is None:
        return None
    label = str(label).strip()[:MAX_LABEL_LEN]
    return label or None


def _make_drawing(kind, coords, label):
    if kind not in _MIN_VERTICES:
        return None
    valid = []
    for ra, dec in coords:
        if not (math.isfinite(ra) and math.isfinite(dec)):
            return None
        if abs(dec) > math.pi / 2.0 + 1e-9:
            return None
        valid.append((ra % (2.0 * math.pi), dec))
    if kind == TYPE_POINT:
        valid = valid[:1]
    if len(valid) < _MIN_VERTICES[kind]:
        return None
    return ChartDrawing(kind=kind, coords=valid, label=_normalize_label(label))


def _apply_limits(drawings):
    result = []
    total = 0
    for drawing in drawings:
        if len(result) >= MAX_ITEMS:
            break
        total += len(drawing.coords)
        if total > MAX_TOTAL_VERTICES:
            break
        result.append(drawing)
    return result


def parse_drawings_json(payload):
    """Parse JSON transport format. Invalid items are skipped, limits are enforced."""
    if not payload or len(payload) > MAX_PAYLOAD_LEN:
        return []
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return []
    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    drawings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_coords = item.get('coords')
        if not isinstance(raw_coords, list):
            continue
        try:
            coords = [(float(c[0]), float(c[1])) for c in raw_coords]
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        drawing = _make_drawing(item.get('type'), coords, item.get('label'))
        if drawing:
            drawings.append(drawing)
    return _apply_limits(drawings)


def parse_drawings_compact(value):
    """Parse compact transport format (degrees). Invalid items are skipped, limits are enforced."""
    if not value or len(value) > MAX_PAYLOAD_LEN:
        return []
    drawings = []
    for token in value.split('*'):
        if len(token) < 2:
            continue
        kind = _COMPACT_TYPES.get(token[0])
        body, _, label = token[1:].partition('~')
        try:
            nums = [float(v) for v in body.split('_')]
        except ValueError:
            continue
        if len(nums) % 2 != 0:
            continue
        coords = [(math.radians(nums[i]), math.radians(nums[i + 1])) for i in range(0, len(nums), 2)]
        drawing = _make_drawing(kind, coords, unquote(label) if label else None)
        if drawing:
            drawings.append(drawing)
    return _apply_limits(drawings)


def drawings_to_json(drawings):
    """Serialize parsed drawings to the normalized JSON transport/storage format."""
    return json.dumps({
        'version': 1,
        'items': [
            {'type': d.kind, 'coords': [[ra, dec] for ra, dec in d.coords], 'label': d.label or ''}
            for d in drawings
        ],
    })


def compute_drawings_view(drawings, field_sizes):
    """Return (center_ra, center_dec, fld_size_deg) framing all vertices, or (None, None, None)."""
    vecs = [_radec_to_vec(ra, dec) for d in drawings for ra, dec in d.coords]
    if not vecs:
        return None, None, None
    sx = sum(v[0] for v in vecs)
    sy = sum(v[1] for v in vecs)
    sz = sum(v[2] for v in vecs)
    norm = math.sqrt(sx * sx + sy * sy + sz * sz)
    if norm < 1e-9:
        # Vertices spread around the whole sphere.
        return 0.0, 0.0, field_sizes[-1]
    center = (sx / norm, sy / norm, sz / norm)
    max_dist = max(math.acos(max(-1.0, min(1.0, v[0] * center[0] + v[1] * center[1] + v[2] * center[2])))
                   for v in vecs)
    needed = math.degrees(2.0 * max_dist) * 1.3
    fld_size = next((fs for fs in field_sizes if fs >= needed), field_sizes[-1])
    center_ra, center_dec = _vec_to_radec(center)
    return center_ra, center_dec, fld_size


def get_drawings_from_request():
    payload = request.form.get(DRAWINGS_FORM_FIELD) if request.method == 'POST' else None
    if payload:
        return parse_drawings_json(payload)
    return parse_drawings_compact(request.args.get(DRAWINGS_QUERY_PARAM))


def _radec_to_vec(ra, dec):
    cos_dec = math.cos(dec)
    return cos_dec * math.cos(ra), cos_dec * math.sin(ra), math.sin(dec)


def _vec_to_radec(v):
    x, y, z = v
    return math.atan2(y, x) % (2.0 * math.pi), math.atan2(z, math.hypot(x, y))


def interpolate_great_circle(p1, p2, max_step):
    """Return points along the great circle p1 -> p2 (p1 excluded, p2 included)."""
    v1 = _radec_to_vec(*p1)
    v2 = _radec_to_vec(*p2)
    dot = max(-1.0, min(1.0, v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]))
    omega = math.acos(dot)
    if omega < 1e-9 or max_step <= 0:
        return [p2]
    n = min(64, max(1, int(math.ceil(omega / max_step))))
    sin_omega = math.sin(omega)
    if sin_omega < 1e-9:
        return [p2]
    result = []
    for i in range(1, n + 1):
        t = i / n
        a = math.sin((1.0 - t) * omega) / sin_omega
        b = math.sin(t * omega) / sin_omega
        result.append(_vec_to_radec((a * v1[0] + b * v2[0], a * v1[1] + b * v2[1], a * v1[2] + b * v2[2])))
    return result


class DrawingsRenderer(TrajectoryRenderer):
    """Trajectory renderer that additionally draws user drawings on top of trajectories."""

    def __init__(self, drawings, color=DRAWING_COLOR):
        super().__init__()
        self.drawings = drawings
        self.color = color

    def draw(self, ctx, state):
        super().draw(ctx, state)
        if self.drawings:
            self.draw_drawings(ctx)

    def draw_drawings(self, ctx):
        gfx = ctx.gfx
        cfg = ctx.cfg
        nzopt = not ctx.transf.is_zoptim()
        max_step = max(ctx.field_radius / 40.0, 1e-5)
        fh = gfx.gi_default_font_size

        gfx.set_pen_rgb(self.color)
        gfx.set_fill_rgb(self.color)
        gfx.set_solid_line()
        gfx.set_font(gfx.gi_font, fh)

        for drawing in self.drawings:
            gfx.set_linewidth(cfg.constellation_linewidth * 1.5)
            if drawing.kind == TYPE_POINT:
                ra, dec = drawing.coords[0]
                x, y, z = ctx.transf.equatorial_to_xyz(ra, dec)
                if not (nzopt or z > 0):
                    continue
                r = cfg.font_size * 0.5
                gfx.circle(x, y, r)
                gfx.circle(x, y, r * 0.25, DrawMode.FILL)
                if drawing.label:
                    self.draw_circular_object_label(ctx, x, y, r, drawing.label, fh=fh, set_pen=False)
                continue

            coords = list(drawing.coords)
            if drawing.kind == TYPE_POLYGON:
                coords.append(coords[0])
            prev = ctx.transf.equatorial_to_xyz(*coords[0])
            for i in range(1, len(coords)):
                for pt in interpolate_great_circle(coords[i - 1], coords[i], max_step):
                    cur = ctx.transf.equatorial_to_xyz(*pt)
                    if nzopt or (prev[2] > 0 and cur[2] > 0):
                        gfx.line(prev[0], prev[1], cur[0], cur[1])
                    prev = cur

            if drawing.label:
                x, y, z = ctx.transf.equatorial_to_xyz(*drawing.coords[0])
                if nzopt or z > 0:
                    self.draw_circular_object_label(ctx, x, y, cfg.font_size * 0.5, drawing.label, fh=fh, set_pen=False)


def install_drawings_renderer(engine, drawings):
    if drawings:
        engine.renderers['trajectory'] = DrawingsRenderer(drawings)
