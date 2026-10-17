import unittest
from unittest.mock import patch

from flask import render_template_string

from app import create_app, db
from app.commons.dso_utils import CHART_DOUBLE_STAR_PREFIX
from app.commons.prevnext_utils import create_navigation_wrappers, get_default_chart_iframe_url
from app.models import (
    DeepskyObject,
    DoubleStar,
    User,
    UserObjectList,
    UserObjectListItem,
    UserObjectListItemType,
)


class UserObjectListViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.owner = self._create_user('owner')
        self.public_list = self._create_list('Public list', is_public=True)
        self.private_list = self._create_list('Private list', is_public=False)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_user(name):
        user = User(user_name=name, full_name=name, email=name + '@example.com', password='password', confirmed=True)
        db.session.add(user)
        db.session.commit()
        return user

    def _create_list(self, title, is_public):
        user_object_list = UserObjectList(user_id=self.owner.id, title=title, text='', is_public=is_public)
        db.session.add(user_object_list)
        db.session.commit()
        return user_object_list

    def test_user_user_object_lists_shows_only_public_lists(self):
        response = self.client.get('/user-user-object-lists/{}'.format(self.owner.id))
        self.assertEqual(200, response.status_code)
        html = response.get_data(as_text=True)
        self.assertIn('Public list', html)
        self.assertNotIn('Private list', html)

    def _fill_list(self, user_object_list):
        # DSO and double star intentionally share the same numeric id
        dso = DeepskyObject(id=1, name='NGC1', type='GX', ra=0.1, dec=0.1, mag=10.0)
        double_star = DoubleStar(id=1, common_cat_id='STF1', ra_first=1.0, dec_first=0.5)
        db.session.add_all([dso, double_star])
        dso_item = UserObjectListItem(user_object_list_id=user_object_list.id, item_type=UserObjectListItemType.DSO, order=1)
        dso_item.deepsky_objects.append(dso)
        ds_item = UserObjectListItem(user_object_list_id=user_object_list.id, item_type=UserObjectListItemType.DBL_STAR,
                                     double_star_id=double_star.id, order=2)
        db.session.add_all([dso_item, ds_item])
        db.session.commit()
        return dso, double_star, dso_item

    def test_chart_scene_selects_object_by_prefix(self):
        self._fill_list(self.public_list)

        url = '/user-object-list/{}/chart/scene-v1'.format(self.public_list.id)
        dbl_highlights = self._get_scene_highlights(url + '?obj_id=dbl1')
        # selected object is the first highlight, followed by all list items (incl. the double star)
        self.assertEqual([CHART_DOUBLE_STAR_PREFIX + '1', 'NGC1', CHART_DOUBLE_STAR_PREFIX + '1'], [h['id'] for h in dbl_highlights])

        dso_highlights = self._get_scene_highlights(url + '?obj_id=dso1')
        self.assertEqual('NGC1', dso_highlights[0]['id'])

    def test_navigation_follows_user_object_list(self):
        dso, double_star, _ = self._fill_list(self.public_list)
        url = '/?back=user_object_list&back_id={}'.format(self.public_list.id)

        with self.app.test_request_context(url):
            prev_wrap, _, next_wrap = create_navigation_wrappers(dso)
            self.assertIsNone(prev_wrap)
            self.assertIn('/double-star/{}/'.format(double_star.id), next_wrap.url())
            self.assertIn('back=user_object_list', next_wrap.url())

            prev_wrap, _, next_wrap = create_navigation_wrappers(double_star)
            self.assertIn('/deepskyobject/NGC1/', prev_wrap.url())
            self.assertIsNone(next_wrap)

    def test_navigation_ignores_private_list_for_anonymous(self):
        dso, _, _ = self._fill_list(self.private_list)
        with self.app.test_request_context('/?back=user_object_list&back_id={}'.format(self.private_list.id)):
            prev_wrap, _, next_wrap = create_navigation_wrappers(dso)
        self.assertIsNone(prev_wrap)
        self.assertIsNone(next_wrap)

    def test_back_button_returns_to_user_object_list(self):
        list_url = '/user-object-list/{}/info'.format(self.public_list.id)
        template = "{% from 'macros/back_sky_chart_navig_macros.html' import back_navig_inner %}" \
                   "{{ back_navig_inner('user_object_list', back_id, 'deepskyobjects', embed) }}"
        with self.app.test_request_context('/'):
            for embed in (None, 'fc'):
                html = render_template_string(template, back_id=self.public_list.id, embed=embed)
                self.assertIn(list_url, html)
                self.assertNotIn('/deepskyobjects', html)

    def test_default_chart_iframe_url_for_dso_item(self):
        _, _, dso_item = self._fill_list(self.public_list)
        with self.app.test_request_context('/'):
            url = get_default_chart_iframe_url(dso_item, back='user_object_list', back_id=self.public_list.id)
        self.assertIn('/deepskyobject/NGC1', url)
        self.assertIn('back=user_object_list', url)

    def _get_scene_highlights(self, url):
        with patch('app.main.catalogue.user_object_list_views.build_scene_v1', side_effect=lambda: {'meta': {}}):
            response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        return response.get_json()['objects']['highlights']


if __name__ == '__main__':
    unittest.main()
