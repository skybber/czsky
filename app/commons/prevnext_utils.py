
from flask import (
    request,
    url_for,
)
from flask_login import current_user

from app import db

from app.models import (
    Constellation,
    DeepskyObject,
    DoubleStar,
    DoubleStarList,
    ObservingSession,
    DsoList,
    Observation,
    ObservedList,
    ObsSessionPlanRun,
    ObservationTargetType,
    SessionPlan,
    Star,
    StarList,
    WishList,
)

from app.commons.permission_utils import allow_view_session_plan

OBJ_ID_DSO_PREFIX = 'dso'
OBJ_ID_DOUBLE_STAR_PREFIX = 'dbl'
OBJ_ID_STAR_PREFIX = 'star'


class PrevNextWrapper:
    def __init__(self, sky_obj, label, tab):
        self._sky_obj = sky_obj
        self._label = label
        self._tab = tab

    def url(self):
        embed = request.args.get('embed')
        season = request.args.get('season')
        back = request.args.get('back')
        back_id = request.args.get('back_id')

        if type(self._sky_obj) == DeepskyObject:
            return url_for('main_deepskyobject.deepskyobject_seltab', dso_id=self._sky_obj.name, seltab=self._tab, back=back, back_id=back_id, season=season, embed=embed)
        if type(self._sky_obj) == Star:
            return url_for('main_star.star_chart', star_id=self._sky_obj.id, back=back, back_id=back_id, season=season, embed=embed)
        if type(self._sky_obj) == DoubleStar:
            return url_for('main_double_star.double_star_seltab', double_star_id=self._sky_obj.id, seltab=self._tab, back=back, back_id=back_id, season=season, embed=embed)

    def top_url(self):
        embed = request.args.get('embed')
        season = request.args.get('season')
        back = request.args.get('back')
        back_id = request.args.get('back_id')

        if type(self._sky_obj) == DeepskyObject:
            obj_id = OBJ_ID_DSO_PREFIX + str(self._sky_obj.id)
        elif type(self._sky_obj) == DoubleStar:
            obj_id = OBJ_ID_DOUBLE_STAR_PREFIX + str(self._sky_obj.id)
        elif type(self._sky_obj) == Star:
            obj_id = OBJ_ID_STAR_PREFIX + str(self._sky_obj.id)
        else:
            obj_id = '' + str(self._sky_obj.id)

        if back == 'observation':
            return url_for('main_observing_session.observing_session_chart', observing_session_id=back_id, obj_id=obj_id, back=back, back_id=back_id, season=season, splitview='true')
        if back == 'wishlist':
            return url_for('main_wishlist.wish_list_chart', obj_id=obj_id, back=back, back_id=back_id, season=season, splitview='true')
        if back == 'session_plan':
            return url_for('main_sessionplan.session_plan_chart', session_plan_id=back_id, obj_id=obj_id, back=back, back_id=back_id, season=season, splitview='true')
        if back == 'dso_list':
            return url_for('main_dso_list.dso_list_chart', dso_list_id=back_id, dso_id=self._sky_obj.id, back=back, back_id=back_id, season=season, splitview='true')

        if type(self._sky_obj) == DeepskyObject:
            return url_for('main_deepskyobject.deepskyobject_chart', dso_id=self._sky_obj.name, back=back, back_id=back_id, season=season, splitview='true')

        return ''

    def label(self):
        if self._label:
            return self._label
        if type(self._sky_obj) == DeepskyObject:
            return self._sky_obj.denormalized_name()
        if type(self._sky_obj) == Star:
            if self._sky_obj.var_id is not None:
                return self._sky_obj.var_id
            if self._sky_obj.hd is not None:
                return 'HD' + self._sky_obj.hd
            return ''
        if type(self._sky_obj) == DoubleStar:
            return self._sky_obj.common_cat_id


def parse_prefix_obj_id(url_obj_id):
    if url_obj_id:
        prefix = None
        if url_obj_id.startswith(OBJ_ID_DSO_PREFIX):
            prefix = OBJ_ID_DSO_PREFIX
        elif url_obj_id.startswith(OBJ_ID_DOUBLE_STAR_PREFIX):
            prefix = OBJ_ID_DOUBLE_STAR_PREFIX
        elif url_obj_id.startswith(OBJ_ID_STAR_PREFIX):
            prefix = OBJ_ID_STAR_PREFIX
        if prefix:
            try:
                obj_id = int(url_obj_id[len(prefix):])
                return prefix, obj_id
            except ValueError:
                pass
    return None, None


def find_by_url_obj_id_in_list(url_obj_id, list):
    if list is not None and url_obj_id is not None:
        prefix, obj_id = parse_prefix_obj_id(url_obj_id)
        if prefix == OBJ_ID_DSO_PREFIX:
            return next((x for x in list if x.dso_id == obj_id), None)
        if prefix == OBJ_ID_DOUBLE_STAR_PREFIX:
            return next((x for x in list if x.double_star_id == obj_id), None)
    return None


def get_default_chart_iframe_url(obj_item, back, back_id=None):
    if obj_item is not None:
        if type(obj_item) == Observation:
            if obj_item.target_type == ObservationTargetType.DSO:
                # special handling for multiple dso in obserrvation
                dso = obj_item.deepsky_objects[0] if len(obj_item.deepsky_objects) > 0 else None
                if dso:
                    return url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back=back, back_id=back_id, embed='fc', allow_back='true')
                return None
        elif obj_item.dso_id is not None:
            return url_for('main_deepskyobject.deepskyobject_info', dso_id=obj_item.deepsky_object.name, back=back, back_id=back_id, embed='fc', allow_back='true')
        if obj_item.double_star_id is not None:
            return url_for('main_double_star.double_star_info', double_star_id=obj_item.double_star_id, back=back, back_id=back_id, embed='fc', allow_back='true')
    return None


def _unwrap(item):
    if item is not None:
        if item.dso_id is not None:
            return item.deepsky_object
        if item.double_star_id is not None:
            return item.double_star
    return None


def _get_prev_next_from_double_star_list(double_star_list, double_star):
    sorted_list = sorted(double_star_list.double_star_list_items, key=lambda x: x.item_id)
    constell_ids = Constellation.get_season_constell_ids(request.args.get('season', None))
    for i, item in enumerate(sorted_list):
        if item.double_star_id == double_star.id:
            for prev_item in reversed(sorted_list[0:i]):
                if constell_ids is None or prev_item.double_star.constellation_id in constell_ids:
                    break
            else:
                prev_item = None
            for next_item in sorted_list[i+1:]:
                if constell_ids is None or next_item.double_star.constellation_id in constell_ids:
                    break
            else:
                next_item = None
            return prev_item, next_item
    return None, None


def _get_prev_next_from_star_list(star_list, star):
    sorted_list = sorted(star_list.star_list_items, key=lambda x: x.item_id)
    constell_ids = Constellation.get_season_constell_ids(request.args.get('season', None))
    for i, item in enumerate(sorted_list):
        if item.star_id == star.id:
            for prev_item in reversed(sorted_list[0:i]):
                if constell_ids is None or prev_item.star.constellation_id in constell_ids:
                    break
            else:
                prev_item = None
            for next_item in sorted_list[i+1:]:
                if constell_ids is None or next_item.star.constellation_id in constell_ids:
                    break
            else:
                next_item = None
            return prev_item, next_item
    return None, None


def _get_prev_next_from_dso_list(dso_list, dso):
    sorted_list = sorted(dso_list.dso_list_items, key=lambda x: x.item_id)
    constell_ids = Constellation.get_season_constell_ids(request.args.get('season', None))
    for i, item in enumerate(sorted_list):
        if item.dso_id == dso.id:
            for prev_item in reversed(sorted_list[0:i]):
                if constell_ids is None or prev_item.deepsky_object.constellation_id in constell_ids:
                    break
            else:
                prev_item = None
            for next_item in sorted_list[i+1:]:
                if constell_ids is None or next_item.deepsky_object.constellation_id in constell_ids:
                    break
            else:
                next_item = None
            return prev_item, next_item
    return None, None


def _get_prev_next_from_observing_session(observing_session, sky_obj):
    observation_list = sorted(observing_session.observations, key=lambda x: x.id)
    prev_item = None
    next_item = None
    find_next = False
    for observation in observation_list:
        if observation.target_type == ObservationTargetType.DSO:
            for dso in observation.deepsky_objects:
                if type(sky_obj) is DeepskyObject and dso.id == sky_obj.id:
                    find_next = True
                elif not find_next:
                    prev_item = dso
                else:
                    next_item = dso
                    return prev_item, next_item
        elif observation.target_type == ObservationTargetType.DBL_STAR:
            if type(sky_obj) is DoubleStar and observation.double_star_id == sky_obj.id:
                find_next = True
            elif not find_next:
                prev_item = observation.double_star
            else:
                next_item = observation.double_star
                return prev_item, next_item
    return prev_item, next_item


def _get_prev_next_from_common_list(common_list, sky_obj):
    sorted_list = sorted(common_list, key=lambda x: x.id)
    constell_ids = Constellation.get_season_constell_ids(request.args.get('season', None))
    for i, item in enumerate(sorted_list):
        if type(sky_obj) == DeepskyObject and item.dso_id == sky_obj.id or \
           type(sky_obj) == DoubleStar and item.double_star_id == sky_obj.id:
            for prev_item in reversed(sorted_list[0:i]):
                if constell_ids is None:
                    break
                if prev_item.dso_id is not None and prev_item.deepsky_object.constellation_id in constell_ids:
                    break
                if prev_item.double_star_id is not None and prev_item.double_star.constellation_id in constell_ids:
                    break
            else:
                prev_item = None
            for next_item in sorted_list[i+1:]:
                if constell_ids is None:
                    break
                if next_item.dso_id is not None and next_item.deepsky_object.constellation_id in constell_ids:
                    break
                if next_item.double_star_id is not None and next_item.double_star.constellation_id in constell_ids:
                    break
            else:
                next_item = None
            return _unwrap(prev_item), _unwrap(next_item)
    return None, None


def create_prev_next_wrappers(sky_obj, tab=None):
    back = request.args.get('back')
    back_id = request.args.get('back_id')

    prev_obj = None
    next_obj = None
    prev_label = None
    next_label = None

    if back == 'observation':
        observing_session = ObservingSession.query.filter_by(id=back_id).first()
        if observing_session and (observing_session.is_public or observing_session.user_id == current_user.id):
            prev_obj, next_obj = _get_prev_next_from_observing_session(observing_session, sky_obj)
    elif back == 'stobservation':
        pass
    elif back == 'constell_dso':
        dso = sky_obj
        constell_dsos = DeepskyObject.query.filter_by(constellation_id=dso.constellation_id, master_id=None) \
            .order_by(DeepskyObject.mag) \
            .all()
        num_dsos = len(constell_dsos)
        for dso_idx in range(num_dsos):
            constell_dso = constell_dsos[dso_idx]
            if constell_dso.id == dso.id:
                prev_obj, next_obj = None, None
                if dso_idx > 0:
                    prev_obj = constell_dsos[dso_idx - 1]
                if dso_idx < num_dsos - 1:
                    next_obj = constell_dsos[dso_idx + 1]
                break
    elif back == 'wishlist':
        if current_user.is_authenticated:
            wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
            prev_obj, next_obj = _get_prev_next_from_common_list(wish_list.wish_list_items, sky_obj)
    elif back == 'observed_list':
        if current_user.is_authenticated:
            observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
            prev_obj, next_obj = _get_prev_next_from_common_list(observed_list.observed_list_items, sky_obj)
    elif back == 'session_plan' and back_id is not None:
        session_plan = SessionPlan.query.filter_by(id=back_id).first()
        if allow_view_session_plan(session_plan):
            prev_obj, next_obj = _get_prev_next_from_common_list(session_plan.session_plan_items, sky_obj)
    elif back == 'running_plan' and back_id is not None:
        observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
        if observation_plan_run and allow_view_session_plan(observation_plan_run.session_plan):
            prev_obj, next_obj = _get_prev_next_from_common_list(observation_plan_run.session_plan.session_plan_items, sky_obj)
    elif back == 'dso_list' and back_id is not None:
        dso_list = DsoList.query.filter_by(id=back_id).first()
        if dso_list:
            prev_item, next_item = _get_prev_next_from_dso_list(dso_list, sky_obj)
            prev_label = str(prev_item.item_id) if prev_item else None
            next_label = str(next_item.item_id) if next_item else None
            prev_obj = prev_item.deepsky_object if prev_item else None
            next_obj = next_item.deepsky_object if next_item else None
    elif back == 'star_list' and back_id is not None:
        star_list = StarList.query.filter_by(id=back_id).first()
        if star_list:
            prev_item, next_item = _get_prev_next_from_star_list(star_list, sky_obj)
            prev_obj = prev_item.star if prev_item else None
            next_obj = next_item.star if next_item else None
    elif back == 'double_star_list' and back_id is not None:
        double_star_list = DoubleStarList.query.filter_by(id=back_id).first()
        if double_star_list:
            prev_item, next_item = _get_prev_next_from_double_star_list(double_star_list, sky_obj)
            prev_obj = prev_item.double_star if prev_item else None
            next_obj = next_item.double_star if next_item else None
    else:
        if type(sky_obj) == DeepskyObject:
            prev_obj, next_obj = sky_obj.get_prev_next_dso()
            prev_label = prev_obj.catalog_number() if prev_obj else None
            next_label = next_obj.catalog_number() if next_obj else None

    prev_wrapper = PrevNextWrapper(prev_obj, prev_label, tab) if prev_obj else None
    next_wrapper = PrevNextWrapper(next_obj, next_label, tab) if next_obj else None

    return prev_wrapper, next_wrapper
