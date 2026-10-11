import unittest
from datetime import datetime

from app import create_app, db
from app.models import (
    DoubleStar,
    DoubleStarList,
    DoubleStarListItem,
    Eyepiece,
    Observation,
    ObservationTargetType,
    ObservedList,
    ObservingSession,
    ObsSessionPlanRun,
    Role,
    SessionPlan,
    Telescope,
    User,
    UserDoubleStarDescription,
    WishList,
)


class DoubleStarViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        # isolate tests from editor settings in local config.env
        for key in ('EDITOR_USER_NAME_CS', 'EDITOR_USER_NAME_EN', 'ALL_EDITORS_USER_NAMES_CS', 'ALL_EDITORS_USER_NAMES_EN'):
            self.app.config[key] = None
        self.app.config['EDITOR_USER_NAME_CS'] = 'editor'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

        self.owner = self._create_user('owner')
        self.other_user = self._create_user('other-user')
        self.double_star = DoubleStar(wds_number='00001+0001', common_cat_id='STF 1', components='AB',
                                      mag_first=5.0, mag_second=6.0, delta_mag=1.0, separation=10.0,
                                      ra_first=0.1, dec_first=0.1)
        db.session.add(self.double_star)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_user(name, role_name=None):
        user = User(user_name=name, full_name=name, email=name + '@example.com', password='password', confirmed=True)
        if role_name:
            user.role = Role.query.filter_by(name=role_name).first()
        db.session.add(user)
        db.session.commit()
        return user

    def _login(self, user):
        response = self.client.post('/account/login', data={'email': user.email, 'password': 'password'})
        self.assertEqual(302, response.status_code)

    def _create_active_session(self, user):
        observing_session = ObservingSession(user_id=user.id, title='Night', date_from=datetime.now(), date_to=datetime.now(),
                                             is_active=True, create_by=user.id, update_by=user.id)
        db.session.add(observing_session)
        db.session.commit()
        return observing_session

    def test_info_ignores_other_users_wish_and_observed_lists(self):
        wish_list = WishList.create_get_wishlist_by_user_id(self.other_user.id)
        db.session.add(wish_list.create_new_double_star_item(self.double_star.id))
        observed_list = ObservedList.create_get_observed_list_by_user_id(self.other_user.id)
        db.session.add(observed_list.create_new_double_star_item(self.double_star.id))
        db.session.commit()

        self._login(self.owner)
        response = self.client.get('/double-star/{}/info'.format(self.double_star.id))
        self.assertEqual(200, response.status_code)
        context = self._last_template_context
        self.assertEqual([], context['wish_list'])
        self.assertEqual([], context['observed_list'])

    def test_info_shows_own_wish_list(self):
        wish_list = WishList.create_get_wishlist_by_user_id(self.owner.id)
        db.session.add(wish_list.create_new_double_star_item(self.double_star.id))
        db.session.commit()

        self._login(self.owner)
        response = self.client.get('/double-star/{}/info'.format(self.double_star.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual([self.double_star.id], self._last_template_context['wish_list'])

    def test_observations_tab_lists_own_observations(self):
        observing_session = self._create_active_session(self.owner)
        observing_session.is_active = False
        db.session.add(Observation(observing_session_id=observing_session.id, double_star_id=self.double_star.id,
                                   target_type=ObservationTargetType.DBL_STAR, notes='split',
                                   date_from=datetime.now(), date_to=datetime.now()))
        db.session.commit()

        self._login(self.owner)
        response = self.client.get('/double-star/{}/observations'.format(self.double_star.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(self._last_template_context['observations']))

    def test_observation_log_update_saves_equipment(self):
        observing_session = self._create_active_session(self.owner)
        telescope = Telescope(user_id=self.owner.id, name='Dob', is_active=True, is_deleted=False)
        eyepiece = Eyepiece(user_id=self.owner.id, name='Nagler', is_active=True, is_deleted=False)
        db.session.add_all([telescope, eyepiece])
        db.session.add(Observation(observing_session_id=observing_session.id, double_star_id=self.double_star.id,
                                   target_type=ObservationTargetType.DBL_STAR, notes='',
                                   date_from=datetime.now(), date_to=datetime.now()))
        db.session.commit()

        self._login(self.owner)
        response = self.client.post('/double-star/{}/observation-log'.format(self.double_star.id), data={
            'notes': 'nice pair',
            'telescope': telescope.id,
            'eyepiece': eyepiece.id,
            'date_from': datetime.now().strftime('%d/%m/%Y'),
            'time_from': '22:30',
        })
        self.assertEqual(302, response.status_code)

        observation = observing_session.find_observation_by_double_star_id(self.double_star.id)
        self.assertIsNotNone(observation)
        self.assertEqual('nice pair', observation.notes)
        self.assertEqual(telescope.id, observation.telescope_id)
        self.assertEqual(eyepiece.id, observation.eyepiece_id)

    def test_edit_uses_description_in_current_language(self):
        editor = self._create_user('editor', role_name='Editor')
        en_descr = UserDoubleStarDescription(double_star_id=self.double_star.id, user_id=editor.id, lang_code='en',
                                             common_name='English', text='english text')
        db.session.add(en_descr)
        db.session.commit()

        self._login(editor)
        response = self.client.post('/double-star/{}/edit'.format(self.double_star.id),
                                    data={'common_name': 'Czech', 'text': 'cesky text', 'goback': 'false'})
        self.assertEqual(302, response.status_code)

        self.assertEqual('english text', db.session.get(UserDoubleStarDescription, en_descr.id).text)
        cs_descr = UserDoubleStarDescription.query.filter_by(double_star_id=self.double_star.id, lang_code='cs').first()
        self.assertIsNotNone(cs_descr)
        self.assertEqual('cesky text', cs_descr.text)

    def test_edit_without_configured_editor_returns_404(self):
        self.app.config['EDITOR_USER_NAME_CS'] = None
        editor = self._create_user('editor', role_name='Editor')
        self._login(editor)
        self.assertEqual(404, self.client.get('/double-star/{}/edit'.format(self.double_star.id)).status_code)

    def test_anonymous_with_running_plan_back_param(self):
        observing_session = self._create_active_session(self.owner)
        session_plan = SessionPlan(user_id=self.owner.id, title='Plan')
        db.session.add(session_plan)
        db.session.commit()
        plan_run = ObsSessionPlanRun(observing_session_id=observing_session.id, session_plan_id=session_plan.id)
        db.session.add(plan_run)
        db.session.commit()

        query = '?back=running_plan&back_id={}'.format(plan_run.id)
        self.assertEqual(200, self.client.get('/double-star/{}/info{}'.format(self.double_star.id, query)).status_code)
        self.assertEqual(404, self.client.get('/double-star/{}/observation-log{}'.format(self.double_star.id, query)).status_code)

    def test_double_star_list_search_is_independent_and_normalized(self):
        double_star_list = DoubleStarList(name='test-list', long_name='Test list')
        db.session.add(double_star_list)
        db.session.commit()
        db.session.add(DoubleStarListItem(double_star_list_id=double_star_list.id, double_star_id=self.double_star.id, item_id=1))
        db.session.commit()

        # search in global double star catalogue must not leak into the list search
        self.client.post('/double-stars', data={'q': 'STF 999'})
        self.client.get('/double-star-list/{}/info'.format(double_star_list.id))
        self.assertIsNone(self._last_template_context['search_form'].q.data)

        self.client.post('/double-star-list/{}/info'.format(double_star_list.id), data={'q': 'STF1'})
        self.client.get('/double-star-list/{}/info'.format(double_star_list.id), query_string={'page': 1})
        self.assertEqual([self.double_star.id], [item.double_star_id for item in self._last_template_context['double_star_list_items']])

    # --- helpers -----------------------------------------------------------------------------

    @property
    def _last_template_context(self):
        return self._recorded[-1][1]

    def run(self, result=None):
        from flask import template_rendered
        self._recorded = []

        def record(sender, template, context, **extra):
            self._recorded.append((template, context))

        template_rendered.connect(record)
        try:
            return super().run(result)
        finally:
            template_rendered.disconnect(record)


if __name__ == '__main__':
    unittest.main()
