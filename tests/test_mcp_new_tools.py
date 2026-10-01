import math
import unittest
from datetime import date, datetime, timedelta

import pytz

from app import create_app, db
from app.main.usersettings.mcp_token_service import SUPPORTED_SCOPES
from app.mcp import astro_common, catalogue_payloads, equipment_payloads, location_payloads
from app.mcp import observation_log_payloads, observing_session_payloads
from app.mcp.observation_log_payloads import parse_observation_object_id
from app.models import (
    DeepskyObject,
    DoubleStar,
    DsoList,
    DsoListItem,
    Eyepiece,
    Location,
    Observation,
    ObservationTargetType,
    ObservedList,
    ObservingSession,
    Telescope,
    User,
)

PRAGUE = pytz.timezone("Europe/Prague")


class _McpDbTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.user = self._create_user('mcp-user')
        self.other_user = self._create_user('mcp-other')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_user(name):
        user = User(user_name=name, full_name=name, email=f'{name}@example.com', password='password', confirmed=True)
        db.session.add(user)
        db.session.commit()
        return user

    def _kwargs(self, user_id=None):
        return {
            'user_id': user_id or self.user.id,
            'require_scope_if_available_func': lambda _scope: None,
            'required_scope': 'test:read',
            'resolve_mcp_user_id_func': lambda user_id: user_id,
            'get_app': lambda: self.app,
        }

    @staticmethod
    def _location(name, lat, lon, user_id=None, is_public=True):
        location = Location(name=name, latitude=lat, longitude=lon, elevation=0, user_id=user_id,
                            is_public=is_public, is_for_observation=True)
        db.session.add(location)
        db.session.commit()
        return location

    @staticmethod
    def _dso(name, dso_type='GX', mag=10.0, master_id=None):
        dso = DeepskyObject(name=name, type=dso_type, mag=mag, ra=1.0, dec=0.5, master_id=master_id)
        db.session.add(dso)
        db.session.commit()
        return dso


class LocationFindTestCase(_McpDbTestCase):
    def setUp(self):
        super().setUp()
        self.own = self._location('Own garden', 50.0, 14.0, user_id=self.user.id, is_public=False)
        self.used = self._location('Dark site', 49.0, 15.0)
        self.near = self._location('Near hill', 49.91, 14.80)
        self.hidden = self._location('Other private', 49.91, 14.79, user_id=self.other_user.id, is_public=False)
        db.session.add(ObservingSession(user_id=self.user.id, title='s', location_id=self.used.id,
                                        date_from=datetime(2026, 9, 1, 21), date_to=datetime(2026, 9, 2, 2)))
        db.session.commit()

    def _find(self, **kwargs):
        params = {'query': None, 'near': None, 'radius_km': None, 'limit': None}
        params.update(kwargs)
        return location_payloads.location_find_payload(**params, **self._kwargs())

    def test_my_locations_lists_used_first_then_own(self):
        result = self._find()
        self.assertEqual('mine', result['mode'])
        self.assertEqual(['Dark site', 'Own garden'], [loc['name'] for loc in result['locations']])
        self.assertEqual(1, result['locations'][0]['useCount'])
        self.assertTrue(result['locations'][1]['isOwn'])

    def test_search_does_not_return_private_locations_of_others(self):
        result = self._find(query='private')
        self.assertFalse(result['found'])
        self.assertEqual('Near hill', self._find(query='hill')['locations'][0]['name'])

    def test_near_sorts_by_distance_and_respects_radius(self):
        result = self._find(near='49.9,14.8', radius_km=20)
        self.assertEqual(['Near hill'], [loc['name'] for loc in result['locations']])
        self.assertLess(result['locations'][0]['distanceKm'], 2)
        self.assertEqual('invalid_near', self._find(near='nonsense')['reason'])

    def test_resolve_user_location_defaults_to_last_used(self):
        resolved = astro_common.resolve_user_location(self.user.id, None)
        self.assertEqual(self.used.id, resolved['locationId'])
        resolved = astro_common.resolve_user_location(self.user.id, '50.5,14.5')
        self.assertIsNone(resolved['locationId'])
        self.assertAlmostEqual(50.5, resolved['latitude'])
        with self.assertRaises(astro_common.McpLookupError) as ctx:
            astro_common.resolve_user_location(self.other_user.id, None)
        self.assertEqual('location_required', ctx.exception.reason)


class LocationMadePrivateTestCase(_McpDbTestCase):
    def test_location_made_private_by_owner_is_no_longer_exposed(self):
        foreign = self._location('Shared site', 49.5, 15.5, user_id=self.other_user.id, is_public=True)
        session = ObservingSession(user_id=self.user.id, title='s', location_id=foreign.id,
                                   date_from=datetime(2026, 9, 1, 21), date_to=datetime(2026, 9, 2, 2))
        db.session.add(session)
        db.session.commit()
        self.assertEqual(foreign.id, astro_common.resolve_user_location(self.user.id, None)['locationId'])

        foreign.is_public = False
        db.session.commit()

        mine = location_payloads.location_find_payload(query=None, near=None, radius_km=None, limit=None,
                                                       **self._kwargs())
        self.assertEqual([], mine['locations'])
        with self.assertRaises(astro_common.McpLookupError):
            astro_common.resolve_user_location(self.user.id, None)
        listed = observing_session_payloads.observing_session_list_payload(
            date_from=None, date_to=None, limit=20, offset=0, **self._kwargs(),
        )
        self.assertIsNone(listed['observingSessions'][0]['locationName'])


class EquipmentListTestCase(_McpDbTestCase):
    def test_lists_only_active_own_equipment_default_first(self):
        db.session.add_all([
            Telescope(user_id=self.user.id, name='Refractor', aperture_mm=80, focal_length_mm=480),
            Telescope(user_id=self.user.id, name='Dobson', aperture_mm=250, focal_length_mm=1200, is_default=True),
            Telescope(user_id=self.user.id, name='Sold', is_active=False),
            Telescope(user_id=self.other_user.id, name='Foreign'),
            Eyepiece(user_id=self.user.id, name='Nagler 13', focal_length_mm=13),
        ])
        db.session.commit()

        result = equipment_payloads.equipment_list_payload(include_inactive=False, **self._kwargs())

        self.assertEqual(['Dobson', 'Refractor'], [t['name'] for t in result['telescopes']])
        self.assertEqual(4.8, result['telescopes'][0]['focalRatio'])
        self.assertEqual('Nagler 13', result['eyepieces'][0]['name'])
        with_inactive = equipment_payloads.equipment_list_payload(include_inactive=True, **self._kwargs())
        self.assertEqual(3, len(with_inactive['telescopes']))


class ObservationReadTestCase(_McpDbTestCase):
    def setUp(self):
        super().setUp()
        self.m13 = self._dso('M13', 'GC', 5.8)
        self.m57 = self._dso('M57', 'PN', 8.8)
        self.session = ObservingSession(user_id=self.user.id, title='Night', date_from=datetime(2026, 8, 1, 21),
                                        date_to=datetime(2026, 8, 2, 2), notes='clear')
        db.session.add(self.session)
        db.session.commit()
        for dso, hour in ((self.m13, 22), (self.m57, 23)):
            observation = Observation(user_id=self.user.id, observing_session_id=self.session.id,
                                      date_from=datetime(2026, 8, 1, hour), date_to=datetime(2026, 8, 1, hour),
                                      target_type=ObservationTargetType.DSO, notes=f'{dso.name} ' + 'x' * 300)
            observation.deepsky_objects.append(dso)
            db.session.add(observation)
        db.session.add(ObservingSession(user_id=self.other_user.id, title='Foreign',
                                        date_from=datetime(2026, 8, 1, 21), date_to=datetime(2026, 8, 2, 2)))
        db.session.commit()

    def _list_observations(self, **kwargs):
        params = {'object_id': None, 'query': None, 'observing_session_id': None, 'date_from': None,
                  'date_to': None, 'limit': 20, 'offset': 0}
        params.update(kwargs)
        return observation_log_payloads.observation_log_list_payload(
            **params, **self._kwargs(),
            parse_observation_object_id_func=parse_observation_object_id,
            resolve_global_object_func=lambda _q: None,
        )

    def test_observation_list_filters_by_object_and_shortens_notes(self):
        result = self._list_observations(object_id=f'dso:{self.m57.id}')
        self.assertEqual(1, result['total'])
        entry = result['observations'][0]
        self.assertEqual('M 57', entry['targets'][0]['name'])
        self.assertTrue(entry['notesPreview'].endswith('…'))
        self.assertNotIn('notes', entry)

    def test_observation_list_paginates_newest_first(self):
        result = self._list_observations(limit=1)
        self.assertEqual(2, result['total'])
        self.assertEqual(1, result['nextOffset'])
        self.assertEqual('M 57', result['observations'][0]['targets'][0]['name'])

    def test_observation_get_returns_full_notes_only_for_owner(self):
        observation_id = Observation.query.first().id
        result = observation_log_payloads.observation_log_get_payload(observation_id=observation_id, **self._kwargs())
        self.assertGreater(len(result['observation']['notes']), 300)
        foreign = observation_log_payloads.observation_log_get_payload(
            observation_id=observation_id, **self._kwargs(self.other_user.id),
        )
        self.assertEqual('observation_not_found', foreign['reason'])

    def _upsert(self, **kwargs):
        params = {'object_id': f'dso:{self.m13.id}', 'query': None, 'observing_session_id': self.session.id,
                  'notes': None, 'date_from': None, 'telescope_id': None, 'eyepiece_id': None, 'filter_id': None}
        params.update(kwargs)
        return observation_log_payloads.observation_log_upsert_payload(
            **params, **self._kwargs(),
            resolve_global_object_func=lambda _q: None,
            parse_observation_object_id_func=parse_observation_object_id,
        )

    def test_upsert_rejects_equipment_of_another_user(self):
        foreign = Telescope(user_id=self.other_user.id, name='Secret scope')
        own = Telescope(user_id=self.user.id, name='My scope')
        db.session.add_all([foreign, own])
        db.session.commit()

        rejected = self._upsert(telescope_id=foreign.id)
        self.assertFalse(rejected['upserted'])
        self.assertEqual('telescope_not_found', rejected['reason'])

        accepted = self._upsert(telescope_id=own.id)
        self.assertTrue(accepted['upserted'])

    def test_foreign_equipment_in_existing_data_is_not_exposed(self):
        foreign = Telescope(user_id=self.other_user.id, name='Secret scope')
        db.session.add(foreign)
        db.session.commit()
        observation = Observation.query.first()
        observation.telescope_id = foreign.id
        db.session.commit()

        result = observation_log_payloads.observation_log_get_payload(observation_id=observation.id, **self._kwargs())
        self.assertIsNone(result['observation']['telescope'])

    def test_observing_session_list_and_get(self):
        result = observing_session_payloads.observing_session_list_payload(
            date_from=None, date_to=None, limit=20, offset=0, **self._kwargs(),
        )
        self.assertEqual(1, result['total'])
        self.assertEqual(2, result['observingSessions'][0]['observationCount'])

        detail = observing_session_payloads.observing_session_get_payload(
            observing_session_id=self.session.id, **self._kwargs(),
        )['observingSession']
        self.assertEqual('clear', detail['notes'])
        self.assertEqual(['M 13', 'M 57'], [o['targets'][0]['name'] for o in detail['observations']])


class ObservedAndListProgressTestCase(_McpDbTestCase):
    def setUp(self):
        super().setUp()
        self.messier = DsoList(name='Messier', long_name='Messier catalogue', hidden=False)
        db.session.add(self.messier)
        db.session.commit()
        self.m1 = self._dso('M1', 'BN')
        self.m2 = self._dso('M2', 'GC')
        self.m3 = self._dso('M3', 'GC')
        self.ngc_alias = self._dso('NGC 7089', 'GC', master_id=self.m2.id)
        for number, dso in enumerate((self.m1, self.m2, self.m3), start=1):
            db.session.add(DsoListItem(dso_list_id=self.messier.id, dso_id=dso.id, item_id=number))
        observed = ObservedList.create_get_observed_list_by_user_id(self.user.id)
        db.session.add_all([
            observed.create_new_deepsky_object_item(self.m1.id),
        ])
        db.session.commit()

    def _progress(self, dso_list):
        return catalogue_payloads.dso_list_progress_payload(
            dso_list=dso_list, include_missing=True, missing_limit=200, **self._kwargs(),
        )

    def test_progress_by_name_counts_observed_and_lists_missing(self):
        result = self._progress('Messier')
        self.assertEqual((3, 1, 2), (result['total'], result['observed'], result['missing']))
        self.assertEqual(33.3, result['percent'])
        self.assertEqual(['M 2', 'M 3'], [m['name'] for m in result['missingObjects']])

    def test_progress_counts_object_observed_through_master(self):
        observed = ObservedList.create_get_observed_list_by_user_id(self.user.id)
        db.session.add(observed.create_new_deepsky_object_item(self.m2.id))
        db.session.commit()
        self.assertEqual(2, self._progress(self.messier.id)['observed'])

    def test_unknown_list(self):
        self.assertEqual('dso_list_not_found', self._progress('Nonexistent')['reason'])

    def test_observed_stats_and_list(self):
        stats = catalogue_payloads.observed_stats_payload(**self._kwargs())
        self.assertEqual(1, stats['observedObjects']['total'])
        self.assertEqual({'BN': 1}, stats['observedObjects']['dsoByType'])

        listed = catalogue_payloads.observed_list_payload(object_types=['dso'], limit=10, offset=0, **self._kwargs())
        self.assertEqual('dso', listed['items'][0]['objectType'])
        with self.assertRaises(ValueError):
            catalogue_payloads.observed_list_payload(object_types=['galaxy'], limit=10, offset=0, **self._kwargs())


class DoubleStarFindTestCase(_McpDbTestCase):
    def test_filters_by_separation_and_excludes_observed(self):
        wide = DoubleStar(common_cat_id='WIDE', separation=20.0, mag_first=4.0, mag_second=6.0, delta_mag=2.0,
                          ra_first=5.0, dec_first=0.8)
        close = DoubleStar(common_cat_id='CLOSE', separation=0.5, mag_first=5.0, mag_second=5.5, delta_mag=0.5,
                           ra_first=5.0, dec_first=0.8)
        seen = DoubleStar(common_cat_id='SEEN', separation=10.0, mag_first=3.0, mag_second=7.0, delta_mag=4.0,
                          ra_first=5.0, dec_first=0.8)
        db.session.add_all([wide, close, seen])
        db.session.commit()
        observed = ObservedList.create_get_observed_list_by_user_id(self.user.id)
        db.session.add(observed.create_new_double_star_item(seen.id))
        db.session.commit()

        result = catalogue_payloads.double_star_find_payload(
            constellation=None, mag_max=None, delta_mag_max=None, separation_min=2.0, separation_max=None,
            min_dec=None, not_observed=True, location=None, date=None, limit=10, **self._kwargs(),
        )

        self.assertEqual(['WIDE'], [d['name'] for d in result['doubleStars']])


class AstroCommonTestCase(unittest.TestCase):
    PRAGUE_LOCATION = {
        'locationId': None, 'name': 'Praha', 'latitude': 50.08, 'longitude': 14.42, 'elevation': 0.0,
        'timezone': PRAGUE,
    }

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_rise_transit_set_describes_one_pass_around_midnight(self):
        # M42 in October: rises before midnight, transits before dawn.
        result = astro_common.rise_transit_set(
            self.PRAGUE_LOCATION, date(2026, 10, 10), math.radians(83.82), math.radians(-5.39),
        )
        self.assertEqual('ok', result['status'])
        self.assertTrue(result['rise'] < result['transit'] < result['set'])
        self.assertTrue(result['transit'].startswith('2026-10-11T05:1'))

    def test_transit_just_after_midnight_is_not_skipped(self):
        # Regression: astroplan's grid search skipped a transit a few minutes after the start time.
        location = dict(self.PRAGUE_LOCATION, latitude=48.60437, longitude=14.706959)
        result = astro_common.rise_transit_set(location, date(2022, 10, 27), 0.3757839323648124, 0.6054692619272661)
        self.assertTrue(result['transit'].startswith('2022-10-28T00:0'))

    def test_circumpolar_and_never_rising_objects(self):
        circumpolar = astro_common.rise_transit_set(self.PRAGUE_LOCATION, date(2026, 10, 1), 0.19, math.radians(41.3))
        self.assertEqual('circumpolar', circumpolar['status'])
        self.assertIsNone(circumpolar['rise'])
        southern = astro_common.rise_transit_set(self.PRAGUE_LOCATION, date(2026, 10, 1), 3.5, math.radians(-43.0))
        self.assertEqual('never_rises', southern['status'])
        self.assertIsNone(southern['transit'])

    def test_twilight_falls_back_to_nautical_darkness_in_summer_north(self):
        twilight = astro_common.compute_twilight(55.6, 12.6, date(2026, 6, 21), PRAGUE)
        self.assertEqual('nautical', twilight['darkness'])
        self.assertIsNone(twilight['events']['astronomicalDusk'])
        self.assertLess(twilight['darkFrom'], twilight['darkTo'])

    def test_moonless_windows_subtracts_moon_up_intervals(self):
        start = datetime(2026, 10, 10, 18)
        windows = astro_common.moonless_windows(
            start, start + timedelta(hours=10),
            [(start - timedelta(hours=2), start + timedelta(hours=2)),
             (start + timedelta(hours=5), start + timedelta(hours=6))],
        )
        self.assertEqual(
            [(start + timedelta(hours=2), start + timedelta(hours=5)),
             (start + timedelta(hours=6), start + timedelta(hours=10))],
            windows,
        )


class McpScopesTestCase(unittest.TestCase):
    def test_new_read_scopes_are_supported(self):
        for scope in ('observationlog:read', 'observed:read', 'location:read', 'equipment:read'):
            self.assertIn(scope, SUPPORTED_SCOPES)


if __name__ == '__main__':
    unittest.main()
