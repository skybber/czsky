import unittest
from datetime import datetime
from unittest.mock import patch

import pytz
from astropy.time import Time

from app.mcp.dso_payloads import _parse_time_filter
from app.mcp.server import get_app as get_real_app


class McpDsoPayloadsTestCase(unittest.TestCase):
    def test_parse_time_filter_uses_local_default_date_for_astropy_time(self):
        tz_info = pytz.timezone("Europe/Prague")
        default_dt = tz_info.localize(datetime(2026, 4, 17, 22, 5, 22, 611555))
        for_date = Time(datetime(2026, 4, 17, 0, 0, 0))

        parsed = _parse_time_filter("21:00", for_date, tz_info, default_dt)

        self.assertEqual(parsed.strftime("%Y-%m-%d %H:%M %z"), "2026-04-17 21:00 +0200")

    def test_parse_time_filter_accepts_24_00_as_next_midnight(self):
        tz_info = pytz.timezone("Europe/Prague")
        default_dt = tz_info.localize(datetime(2026, 4, 17, 22, 5, 22, 611555))
        for_date = Time(datetime(2026, 4, 17, 0, 0, 0))

        parsed = _parse_time_filter("24:00", for_date, tz_info, default_dt)

        self.assertEqual(parsed.strftime("%Y-%m-%d %H:%M %z"), "2026-04-18 00:00 +0200")

    def test_parse_time_filter_returns_default_for_invalid_time(self):
        tz_info = pytz.timezone("Europe/Prague")
        default_dt = tz_info.localize(datetime(2026, 4, 17, 22, 5, 22, 611555))

        parsed = _parse_time_filter("invalid", None, tz_info, default_dt)

        self.assertIs(parsed, default_dt)

    def test_parse_time_filter_rejects_invalid_24_hour_variant(self):
        tz_info = pytz.timezone("Europe/Prague")
        default_dt = tz_info.localize(datetime(2026, 4, 17, 22, 5, 22, 611555))
        for_date = Time(datetime(2026, 4, 17, 0, 0, 0))

        parsed = _parse_time_filter("24:30", for_date, tz_info, default_dt)

        self.assertIs(parsed, default_dt)

    def test_dso_find_without_obj_source_does_not_default_to_wishlist(self):
        from app.mcp import dso_payloads

        class _BombQuery:
            def __getattr__(self, _name):
                raise AssertionError("wishlist query should not be used when obj_source is omitted")

        class _DummyQuery:
            def __init__(self, rows):
                self.rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def filter_by(self, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def all(self):
                return self.rows

        dummy_dso = type(
            "DummyDso",
            (),
            {
                "name": "M31",
                "type": "GX",
                "mag": 3.4,
                "constellation_id": None,
            },
        )()

        with get_real_app().app_context():
            from app.models import Catalogue, Constellation, DeepskyObject, WishListItem

            with patch.object(WishListItem, "query", _BombQuery()), \
                 patch.object(DeepskyObject, "query", _DummyQuery([dummy_dso])), \
                 patch.object(Catalogue, "get_catalogue_id_by_cat_code", return_value=None), \
                 patch.object(Constellation, "get_constellation_by_id", return_value=None):
                result = dso_payloads.dso_find_payload(
                    obj_source=None,
                    dso_type=None,
                    maglim=None,
                    constellation=None,
                    min_altitude=5,
                    session_plan_id=None,
                    time_from=None,
                    time_to=None,
                    not_observed=False,
                    max_results=20,
                    user_id=5,
                    require_scope_if_available_func=lambda _scope: None,
                    required_scope="dso:read",
                    resolve_wishlist_user_id_func=lambda user_id: user_id or 0,
                    get_app=get_real_app,
                )

        self.assertTrue(result["found"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["name"], "M31")
