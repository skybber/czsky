import math
import re
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.commons import comet_utils
from app.models import (
    Comet, CometObservation, Observation, ObservedList, ObservedListItem,
    Role, SessionPlan, SessionPlanItem, User, UserObjectList, UserObjectListItem,
    UserObjectListItemType,
)
from config import TestingConfig


class ManualCometsTestCase(unittest.TestCase):
    def setUp(self):
        with patch.multiple(TestingConfig, SQLALCHEMY_DATABASE_URI='sqlite://',
                            SQLALCHEMY_BINDS={'sqm_sql': 'sqlite://'}):
            self.app = create_app('testing', default_locale='en')
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        Role.insert_roles()
        roles = {role.name: role for role in Role.query.all()}
        self.admin = User(user_name='comet-admin', email='comet-admin@example.test', password='password',
                          confirmed=True, role=roles['Administrator'])
        self.user = User(user_name='comet-user', email='comet-user@example.test', password='password',
                         confirmed=True, role=roles['User'])
        self.editor = User(user_name='comet-editor', email='comet-editor@example.test', password='password',
                           confirmed=True, role=roles['Editor'])
        db.session.add_all([self.admin, self.user, self.editor])
        db.session.commit()
        self.client = self.app.test_client()
        self.data = {
            'designation': 'Unpublished comet', 'perihelion_year': '2026', 'perihelion_month': '9',
            'perihelion_day': '20.125', 'perihelion_distance_au': '0.8', 'eccentricity': '1.0',
            'inclination_degrees': '45', 'longitude_of_ascending_node_degrees': '120',
            'argument_of_perihelion_degrees': '70', 'epoch': '2026-09-20',
            'magnitude_g': '', 'magnitude_k': '', 'reference': 'Test elements',
        }

    def tearDown(self):
        comet_utils._get_comet_cached.cache_clear()
        db.session.remove()
        db.drop_all()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()

    def login(self, user):
        self.client.get('/account/logout')
        response = self.client.post('/account/login', data={'email': user.email, 'password': 'password'})
        self.assertEqual(response.status_code, 302)

    def create_comet(self, **overrides):
        self.login(self.admin)
        response = self.client.post('/admin/comets/new', data=dict(self.data, **overrides))
        self.assertEqual(response.status_code, 302, response.data.decode()[:1000])
        return Comet.query.filter_by(is_manual=True).one()

    def test_only_admin_can_access_creation_and_editing(self):
        comet = self.create_comet()
        paths = ['/admin/comets', '/admin/comets/new', '/admin/comets/{}/edit'.format(comet.id)]
        for user in (None, self.user, self.editor):
            self.client.get('/account/logout')
            if user:
                self.login(user)
            for path in paths:
                with self.subTest(user=user.user_name if user else 'anonymous', path=path):
                    self.assertEqual(self.client.get(path).status_code, 403 if user else 302)
                    if path != '/admin/comets':
                        response = self.client.post(path, data=dict(self.data, designation='Unauthorized'))
                        self.assertEqual(response.status_code, 403 if user else 302)
        self.assertEqual(Comet.query.count(), 1)
        self.assertEqual(comet.designation, self.data['designation'])

    def test_admin_can_create_and_edit_without_changing_identity(self):
        comet = self.create_comet()
        comet_id, database_id = comet.comet_id, comet.id
        self.assertIsNone(comet.mag)
        self.assertTrue(math.isfinite(comet.cur_ra))
        self.assertTrue(math.isfinite(comet.cur_tail_pa))
        response = self.client.get('/admin/comets/{}/edit'.format(comet.id))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'2026-09-20', response.data)
        self.assertEqual(self.client.get('/admin/comets').status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        t = datetime(2026, 9, 28, tzinfo=timezone.utc)
        position_before = comet_utils.get_comet_radec(comet_id, t)
        response = self.client.post('/admin/comets/{}/edit'.format(comet.id), data=dict(
            self.data, designation='Renamed comet', inclination_degrees='90', magnitude_g='8', magnitude_k='4'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(comet.comet_id, comet_id)
        self.assertEqual(comet.id, database_id)
        self.assertEqual(comet.designation, 'Renamed comet')
        self.assertTrue(math.isfinite(comet.eval_mag))
        self.assertEqual(comet.mag, comet.eval_mag)
        self.assertNotEqual(position_before, comet_utils.get_comet_radec(comet_id, t))
        response = self.client.post('/admin/comets/{}/edit'.format(comet.id), data=dict(
            self.data, eccentricity='0.5'))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(comet.eval_mag)
        self.assertIsNone(comet.mag)

    def test_manual_lookup_works_without_catalogue_download(self):
        comet = self.create_comet()
        with patch.object(comet_utils, 'get_all_comets', side_effect=AssertionError('External catalogue accessed')):
            row = comet_utils.find_mpc_comet(comet.comet_id)
            self.assertEqual(row.designation, comet.designation)
            self.assertTrue(all(math.isfinite(value) for value in comet_utils.get_comet_radec(
                comet.comet_id, datetime(2026, 9, 28, tzinfo=timezone.utc))))

    def test_anonymous_list_detail_and_chart_include_unknown_brightness(self):
        comet = self.create_comet()
        self.client.get('/account/logout')
        response = self.client.get('/comets', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unpublished comet', response.data)
        response = self.client.get('/comet/{}/info?embed=comets'.format(comet.comet_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unpublished comet', response.data)
        response = self.client.get('/comet/{}/cobs-observations'.format(comet.comet_id), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unpublished comet', response.data)
        with patch('app.main.solarsystem.comet_views.build_scene_v1', return_value={'objects': {}, 'meta': {}}):
            response = self.client.get('/comets/chart/scene-v1?ra=1&dec=0&fsz=23&width=800&height=600')
        self.assertEqual(response.status_code, 200)
        highlights = response.get_json()['objects']['highlights']
        self.assertEqual(highlights[0]['label'], comet.designation)
        self.assertNotIn('mag', highlights[0])

    def test_invalid_elements_are_rejected(self):
        self.login(self.admin)
        for overrides in (
            {'perihelion_distance_au': '0'}, {'perihelion_distance_au': 'nan'},
            {'eccentricity': '-1'}, {'eccentricity': 'inf'}, {'inclination_degrees': '181'},
            {'perihelion_month': '2', 'perihelion_day': '30.1'}, {'perihelion_day': 'nan'},
            {'epoch': '2026-02-30'}, {'magnitude_g': '8'}, {'designation': '   '},
        ):
            with self.subTest(overrides=overrides):
                response = self.client.post('/admin/comets/new', data=dict(self.data, **overrides))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Comet.query.count(), 0)

    def test_csrf_is_required_for_admin_changes(self):
        self.login(self.admin)
        self.app.config['WTF_CSRF_ENABLED'] = True
        self.assertEqual(self.client.post('/admin/comets/new', data=self.data).status_code, 400)
        self.assertEqual(Comet.query.count(), 0)

    def test_import_cannot_overwrite_manual_elements(self):
        comet = self.create_comet()
        row = comet_utils.manual_comet_row(comet)
        row['designation'] = 'External replacement'
        row['eccentricity'] = 0.2
        catalogue = pd.DataFrame([row])
        comet_utils.import_update_comets(catalogue)
        self.assertEqual(comet.designation, self.data['designation'])
        self.assertEqual(comet.eccentricity, 1.0)
        comet_utils.update_comets_positions(catalogue)
        comet_utils.update_evaluated_comet_brightness(catalogue)
        self.assertEqual(comet.eccentricity, 1.0)
        self.assertIsNone(comet.mag)
        merged = comet_utils.include_manual_comets(catalogue)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.iloc[0].designation, self.data['designation'])
        with patch.object(comet_utils, 'all_comets', catalogue), \
                patch.object(comet_utils, 'all_comets_expiration', datetime.max):
            self.assertEqual(comet_utils.get_all_comets().iloc[0].designation, self.data['designation'])

    def test_scheduled_updates_include_manual_comets_missing_from_catalogue(self):
        comet = self.create_comet(magnitude_g='8', magnitude_k='4', eccentricity='1.1')
        comet.cur_ra = None
        comet.eval_mag = None
        db.session.commit()
        catalogue = pd.DataFrame(columns=['comet_id', 'designation'])
        comet_utils.update_comets_positions(catalogue)
        comet_utils.update_evaluated_comet_brightness(catalogue)
        self.assertTrue(math.isfinite(comet.cur_ra))
        self.assertTrue(math.isfinite(comet.eval_mag))

    def test_catalogue_comets_cannot_be_edited_via_manual_form(self):
        self.login(self.admin)
        comet = Comet(comet_id='catalogue-comet', designation='Catalogue comet')
        db.session.add(comet)
        db.session.commit()
        url = '/admin/comets/{}/edit'.format(comet.id)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, data=self.data).status_code, 404)

    def test_failed_orbit_calculation_rolls_back_edit(self):
        comet = self.create_comet()
        with patch('app.admin.views.refresh_manual_comet', side_effect=ValueError('Invalid orbit')):
            response = self.client.post('/admin/comets/{}/edit'.format(comet.id), data=dict(
                self.data, designation='Failed edit'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(comet.designation, self.data['designation'])

    def test_admin_can_confirm_deletion_of_unused_manual_comet(self):
        comet = self.create_comet()
        database_id, public_id = comet.id, comet.comet_id
        url = '/admin/comets/{}/delete'.format(database_id)
        for page in ('/admin/comets', '/admin/comets/{}/edit'.format(database_id)):
            self.assertIn(url.encode(), self.client.get(page).data)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unpublished comet', response.data)
        self.assertIn(b'method="POST"', response.data)
        self.assertIn(b'Cancel', response.data)
        self.assertIsNotNone(db.session.get(Comet, database_id))
        comet_utils.get_comet_radec(public_id, datetime(2026, 9, 28, tzinfo=timezone.utc))
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/admin/comets'))
        self.assertIsNone(db.session.get(Comet, database_id))
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.get('/account/logout')
        with patch.object(comet_utils, 'get_all_comets', side_effect=AssertionError('Catalogue accessed')):
            self.assertEqual(self.client.get('/comet/{}/info'.format(public_id)).status_code, 404)
        self.assertNotIn(b'Unpublished comet', self.client.get('/comets', follow_redirects=True).data)

    def test_only_admin_can_access_or_submit_comet_deletion(self):
        comet = self.create_comet()
        url = '/admin/comets/{}/delete'.format(comet.id)
        for user in (None, self.user, self.editor):
            self.client.get('/account/logout')
            if user:
                self.login(user)
            with self.subTest(user=user.user_name if user else 'anonymous'):
                self.assertEqual(self.client.get(url).status_code, 403 if user else 302)
                self.assertEqual(self.client.post(url).status_code, 403 if user else 302)
                self.assertIsNotNone(db.session.get(Comet, comet.id))

    def test_deletion_requires_valid_csrf_token(self):
        comet = self.create_comet()
        url = '/admin/comets/{}/delete'.format(comet.id)
        self.app.config['WTF_CSRF_ENABLED'] = True
        response = self.client.get(url)
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertIsNotNone(db.session.get(Comet, comet.id))
        self.assertEqual(self.client.post(url, data={'csrf_token': token}).status_code, 302)
        self.assertEqual(Comet.query.count(), 0)

    def test_official_comet_cannot_be_deleted_from_admin(self):
        self.login(self.admin)
        comet = Comet(comet_id='official', designation='Official comet')
        db.session.add(comet)
        db.session.commit()
        url = '/admin/comets/{}/delete'.format(comet.id)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertIsNotNone(db.session.get(Comet, comet.id))

    def test_deletion_preserves_every_kind_of_linked_record(self):
        comet = self.create_comet()
        url = '/admin/comets/{}/delete'.format(comet.id)
        plan = SessionPlan(user_id=self.user.id, title='Private plan')
        observed = ObservedList(user_id=self.user.id)
        objects = UserObjectList(user_id=self.user.id, title='Private list')
        db.session.add_all([plan, observed, objects])
        db.session.commit()
        for model, values, label in (
            (Observation, {'user_id': self.user.id}, b'Observations'),
            (CometObservation, {}, b'COBS observations'),
            (SessionPlanItem, {'session_plan_id': plan.id}, b'Session plans'),
            (ObservedListItem, {'observed_list_id': observed.id}, b'Observed lists'),
            (UserObjectListItem, {'user_object_list_id': objects.id,
                                 'item_type': UserObjectListItemType.COMET}, b'User object lists'),
        ):
            with self.subTest(model=model.__name__):
                # A record may be added after the administrator opens the confirmation page.
                self.assertEqual(self.client.get(url).status_code, 200)
                record = model(comet_id=comet.id, **values)
                db.session.add(record)
                db.session.commit()
                response = self.client.post(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'cannot be deleted', response.data)
                self.assertIn(label, response.data)
                self.assertNotIn(b'type="submit"', response.data)
                self.assertIsNotNone(db.session.get(Comet, comet.id))
                self.assertEqual(db.session.get(model, record.id).comet_id, comet.id)
                db.session.delete(record)
                db.session.commit()

    def test_deletion_rolls_back_when_database_reports_a_reference(self):
        comet = self.create_comet()
        url = '/admin/comets/{}/delete'.format(comet.id)
        with patch.object(db.session, 'commit', side_effect=IntegrityError('DELETE', {}, Exception())):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'still referenced', response.data)
        self.assertIsNotNone(db.session.get(Comet, comet.id))


if __name__ == '__main__':
    unittest.main()
