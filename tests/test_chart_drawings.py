import json
import math
import unittest
from types import SimpleNamespace

from flask import Flask

from app.commons.chart_drawings import (
    DrawingsRenderer,
    MAX_ITEMS,
    MAX_LABEL_LEN,
    MAX_TOTAL_VERTICES,
    TYPE_POINT,
    TYPE_POLYGON,
    TYPE_POLYLINE,
    get_drawings_from_request,
    install_drawings_renderer,
    interpolate_great_circle,
    parse_drawings_compact,
    parse_drawings_json,
)


def _json_payload(items):
    return json.dumps({'version': 1, 'items': items})


class ParseDrawingsJsonTestCase(unittest.TestCase):
    def test_valid_items(self):
        drawings = parse_drawings_json(_json_payload([
            {'type': 'polyline', 'coords': [[1.0, 0.1], [1.1, 0.2]], 'label': ' route '},
            {'type': 'polygon', 'coords': [[1.0, 0.1], [1.1, 0.2], [1.2, 0.1]]},
            {'type': 'point', 'coords': [[2.0, -0.3]], 'label': ''},
        ]))
        self.assertEqual([d.kind for d in drawings], [TYPE_POLYLINE, TYPE_POLYGON, TYPE_POINT])
        self.assertEqual(drawings[0].label, 'route')
        self.assertIsNone(drawings[2].label)
        self.assertEqual(drawings[1].coords[2], (1.2, 0.1))

    def test_invalid_items_skipped(self):
        drawings = parse_drawings_json(_json_payload([
            {'type': 'polygon', 'coords': [[1.0, 0.1], [1.1, 0.2]]},  # too few vertices
            {'type': 'circle', 'coords': [[1.0, 0.1]]},  # unknown type
            {'type': 'point', 'coords': [[1.0, 2.0]]},  # dec out of range
            {'type': 'point', 'coords': [['x', 0.0]]},
            {'type': 'point', 'coords': [[float('nan'), 0.0]]},
            {'type': 'polyline', 'coords': [{'a': 1}, {'b': 2}]},
            'garbage',
            {'type': 'point', 'coords': [[-0.5, 0.0]]},
        ]))
        self.assertEqual(len(drawings), 1)
        self.assertAlmostEqual(drawings[0].coords[0][0], 2 * math.pi - 0.5)

    def test_malformed_payload(self):
        self.assertEqual(parse_drawings_json('not json'), [])
        self.assertEqual(parse_drawings_json('[1, 2]'), [])
        self.assertEqual(parse_drawings_json(''), [])
        self.assertEqual(parse_drawings_json(None), [])

    def test_limits(self):
        many = [{'type': 'point', 'coords': [[1.0, 0.0]]} for _ in range(MAX_ITEMS + 10)]
        self.assertEqual(len(parse_drawings_json(_json_payload(many))), MAX_ITEMS)

        big = [{'type': 'polyline', 'coords': [[0.001 * i, 0.0] for i in range(MAX_TOTAL_VERTICES - 1)]},
               {'type': 'polyline', 'coords': [[1.0, 0.0], [1.1, 0.0]]}]
        self.assertEqual(len(parse_drawings_json(_json_payload(big))), 1)

        long_label = parse_drawings_json(_json_payload([{'type': 'point', 'coords': [[1.0, 0.0]], 'label': 'x' * 500}]))
        self.assertEqual(len(long_label[0].label), MAX_LABEL_LEN)


class ParseDrawingsCompactTestCase(unittest.TestCase):
    def test_valid(self):
        drawings = parse_drawings_compact('L83.6331_22.0145_84.1_-21.2*P10_10_11_10_11_11*T120.5_-5~M%C3%ADsto%2A1')
        self.assertEqual([d.kind for d in drawings], [TYPE_POLYLINE, TYPE_POLYGON, TYPE_POINT])
        self.assertAlmostEqual(drawings[0].coords[0][0], math.radians(83.6331))
        self.assertAlmostEqual(drawings[0].coords[1][1], math.radians(-21.2))
        self.assertEqual(drawings[2].label, 'Místo*1')

    def test_invalid_tokens_skipped(self):
        drawings = parse_drawings_compact('X1_2*L1_2_3*Labc_1*T1_2**L1_2_3_4')
        self.assertEqual(len(drawings), 2)
        self.assertEqual(drawings[0].kind, TYPE_POINT)
        self.assertEqual(drawings[1].kind, TYPE_POLYLINE)

    def test_empty(self):
        self.assertEqual(parse_drawings_compact(None), [])
        self.assertEqual(parse_drawings_compact(''), [])


class DrawingsFromRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_post_form_has_priority(self):
        payload = _json_payload([{'type': 'point', 'coords': [[1.0, 0.0]]}])
        with self.app.test_request_context('/chart/chart-pdf?drw=L1_2_3_4', method='POST',
                                           data={'drawings': payload}):
            drawings = get_drawings_from_request()
        self.assertEqual([d.kind for d in drawings], [TYPE_POINT])

    def test_query_param(self):
        with self.app.test_request_context('/chart/chart-pos-img?drw=L1_2_3_4'):
            drawings = get_drawings_from_request()
        self.assertEqual([d.kind for d in drawings], [TYPE_POLYLINE])

    def test_no_drawings(self):
        with self.app.test_request_context('/chart/chart-pos-img'):
            self.assertEqual(get_drawings_from_request(), [])


class InterpolateGreatCircleTestCase(unittest.TestCase):
    def test_endpoints_and_step(self):
        p1 = (0.0, 0.0)
        p2 = (math.radians(10.0), 0.0)
        pts = interpolate_great_circle(p1, p2, math.radians(1.001))
        self.assertEqual(len(pts), 10)
        self.assertAlmostEqual(pts[-1][0], p2[0])
        self.assertAlmostEqual(pts[-1][1], p2[1])
        for ra, dec in pts:
            self.assertAlmostEqual(dec, 0.0)

    def test_follows_great_circle(self):
        # Midpoint of two points on the same declination lies poleward of that declination.
        dec = math.radians(60.0)
        # Angular distance is ~41.4 deg -> two pieces.
        pts = interpolate_great_circle((0.0, dec), (math.radians(90.0), dec), math.radians(25.0))
        self.assertEqual(len(pts), 2)
        self.assertGreater(pts[0][1], dec)

    def test_identical_points(self):
        self.assertEqual(interpolate_great_circle((1.0, 0.5), (1.0, 0.5), 0.01), [(1.0, 0.5)])


class _RecordingGfx:
    gi_default_font_size = 3.0
    gi_font = 'Times-Roman'

    def __init__(self):
        self.lines = []
        self.circles = []
        self.texts = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def line(self, x1, y1, x2, y2):
        self.lines.append((x1, y1, x2, y2))

    def circle(self, x, y, r, mode=None):
        self.circles.append((x, y, r))

    def text_right(self, x, y, text):
        self.texts.append(text)

    text_left = text_right


class DrawingsRendererTestCase(unittest.TestCase):
    def _ctx(self, zoptim=False):
        transf = SimpleNamespace(
            is_zoptim=lambda: zoptim,
            # Visible hemisphere is dec >= 0 for the zoptim test.
            equatorial_to_xyz=lambda ra, dec: (ra * 100.0, dec * 100.0, 1.0 if dec >= 0 else -1.0),
        )
        cfg = SimpleNamespace(constellation_linewidth=0.3, font_size=3.0, label_color=(0, 0, 0))
        return SimpleNamespace(gfx=_RecordingGfx(), cfg=cfg, transf=transf, field_radius=math.radians(10.0),
                               trajectories=None)

    def test_draws_shapes_and_labels(self):
        drawings = parse_drawings_json(_json_payload([
            {'type': 'polygon', 'coords': [[0.1, 0.1], [0.11, 0.1], [0.11, 0.11]], 'label': 'area'},
            {'type': 'point', 'coords': [[0.2, 0.2]], 'label': 'star'},
        ]))
        ctx = self._ctx()
        DrawingsRenderer(drawings).draw(ctx, None)
        self.assertGreaterEqual(len(ctx.gfx.lines), 3)  # closed polygon -> at least 3 segments
        first = ctx.gfx.lines[0]
        last = ctx.gfx.lines[-1]
        self.assertAlmostEqual(last[2], first[0])
        self.assertAlmostEqual(last[3], first[1])
        self.assertEqual(len(ctx.gfx.circles), 2)  # point ring + center dot
        self.assertEqual(ctx.gfx.texts, ['area', 'star'])

    def test_skips_segments_behind_observer(self):
        drawings = parse_drawings_json(_json_payload([
            {'type': 'polyline', 'coords': [[0.1, -0.1], [0.1, -0.2]]},
            {'type': 'point', 'coords': [[0.1, -0.1]]},
        ]))
        ctx = self._ctx(zoptim=True)
        DrawingsRenderer(drawings).draw(ctx, None)
        self.assertEqual(ctx.gfx.lines, [])
        self.assertEqual(ctx.gfx.circles, [])

    def test_install_only_with_drawings(self):
        engine = SimpleNamespace(renderers={'trajectory': 'orig'})
        install_drawings_renderer(engine, [])
        self.assertEqual(engine.renderers['trajectory'], 'orig')
        install_drawings_renderer(engine, parse_drawings_compact('T1_2'))
        self.assertIsInstance(engine.renderers['trajectory'], DrawingsRenderer)


if __name__ == '__main__':
    unittest.main()
