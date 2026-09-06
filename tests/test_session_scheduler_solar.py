import unittest
from datetime import date, datetime
from types import SimpleNamespace

import pytz

from app import create_app
from app.main.planner.session_scheduler import (
    _get_selected_object_ids,
    get_session_plan_position_datetime,
)
from app.main.planner.sessionplan_views import (
    _get_selection_candidate_url,
    _get_session_plan_item_url,
)


class SessionSchedulerSolarTestCase(unittest.TestCase):
    def test_selected_object_ids_omit_null_values(self):
        session_plan = SimpleNamespace(session_plan_items=[
            SimpleNamespace(comet_id=None),
            SimpleNamespace(comet_id=7),
            SimpleNamespace(comet_id=11),
        ])

        self.assertEqual(_get_selected_object_ids(session_plan, 'comet_id'), {7, 11})

    def test_position_datetime_uses_local_midnight_converted_to_utc(self):
        session_plan = SimpleNamespace(for_date=datetime(2026, 1, 15, 18, 30))

        position_dt = get_session_plan_position_datetime(
            session_plan, pytz.timezone('Europe/Prague')
        )

        self.assertEqual(position_dt, datetime(2026, 1, 14, 23, 0))
        self.assertIsNone(position_dt.tzinfo)

    def test_position_datetime_accepts_date_value(self):
        session_plan = SimpleNamespace(for_date=date(2026, 7, 15))

        position_dt = get_session_plan_position_datetime(
            session_plan, pytz.timezone('Europe/Prague')
        )

        self.assertEqual(position_dt, datetime(2026, 7, 14, 22, 0))

    def test_selection_candidate_urls_support_all_planner_sources(self):
        app = create_app('testing')
        candidates = [
            (SimpleNamespace(object_type='dso', name='M1'), '/deepskyobject/M1/seltab?embed=pl'),
            (SimpleNamespace(object_type='comet', detail_id='0010P'), '/comet/0010P/seltab?embed=pl'),
            (SimpleNamespace(object_type='minor_planet', detail_id='1-Ceres'), '/minor-planet/1-Ceres/seltab?seltab=catalogue_data&embed=pl'),
            (SimpleNamespace(object_type='planet', detail_id='mars'), '/planet/mars/seltab?embed=pl'),
        ]

        with app.test_request_context():
            self.assertEqual(
                [_get_selection_candidate_url(candidate) for candidate, _ in candidates],
                [expected_url for _, expected_url in candidates],
            )

    def test_session_plan_solar_item_urls_match_selection_urls(self):
        app = create_app('testing')
        common_ids = {
            'dso_id': None,
            'double_star_id': None,
            'planet_id': None,
            'minor_planet_id': None,
            'comet_id': None,
        }
        items = [
            (
                SimpleNamespace(
                    **{**common_ids, 'planet_id': 1},
                    planet=SimpleNamespace(iau_code='mars'),
                ),
                '/planet/mars/seltab?embed=pl',
            ),
            (
                SimpleNamespace(
                    **{**common_ids, 'minor_planet_id': 1},
                    minor_planet=SimpleNamespace(url_id=lambda: '1-Ceres'),
                ),
                '/minor-planet/1-Ceres/seltab?seltab=catalogue_data&embed=pl',
            ),
            (
                SimpleNamespace(
                    **{**common_ids, 'comet_id': 1},
                    comet=SimpleNamespace(comet_id='0010P'),
                ),
                '/comet/0010P/seltab?embed=pl',
            ),
        ]

        with app.test_request_context():
            self.assertEqual(
                [_get_session_plan_item_url(item) for item, _ in items],
                [expected_url for _, expected_url in items],
            )


if __name__ == '__main__':
    unittest.main()
