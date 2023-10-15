from flask import (
    request,
)

from flask_login import current_user

from sqlalchemy import or_

from app.models import (
    DeepskyObject,
    DoubleStarList,
    DsoList,
    DsoListItem,
    ObservingSession,
    ObservedList,
    ObservedListItem,
    ObsSessionPlanRun,
    ObservationTargetType,
    SessionPlan,
    SessionPlanItemType,
    WishList,
    WishListItem,
)

from app import db

from app.commons.permission_utils import allow_view_session_plan
from .dso_utils import CHART_DOUBLE_STAR_PREFIX, CHART_COMET_PREFIX, CHART_MINOR_PLANET_PREFIX, CHART_PLANET_PREFIX


def common_highlights_from_wishlist_items(wish_list_items):
    highlights_dso_list = []
    highlights_pos_list = []

    if wish_list_items:
        for item in wish_list_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id), item.double_star.get_common_name()])
    return highlights_dso_list, highlights_pos_list


def common_highlights_from_observed_list_items(observed_list_items):
    highlights_dso_list = []
    highlights_pos_list = []

    if observed_list_items:
        for item in observed_list_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id), item.double_star.get_common_name()])
    return highlights_dso_list, highlights_pos_list


def common_highlights_from_observing_session(observing_session):
    highlights_dso_list = []
    highlights_pos_list = []

    if observing_session:
        for observation in observing_session.observations:
            if observation.target_type == ObservationTargetType.DSO:
                highlights_dso_list.extend(observation.deepsky_objects)
            elif observation.target_type == ObservationTargetType.DBL_STAR:
                highlights_pos_list.append([observation.double_star.ra_first, observation.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(observation.double_star_id), observation.double_star.get_common_name()])
            elif observation.target_type == ObservationTargetType.COMET:
                highlights_pos_list.append([observation.ra, observation.dec, CHART_COMET_PREFIX + str(observation.comet_id), observation.comet.designation])
            elif observation.target_type == ObservationTargetType.M_PLANET:
                highlights_pos_list.append([observation.ra, observation.dec, CHART_MINOR_PLANET_PREFIX + str(observation.minor_planet_id), observation.minor_planet.designation])
            elif observation.target_type == ObservationTargetType.PLANET:
                highlights_pos_list.append([observation.ra, observation.dec, CHART_PLANET_PREFIX + str(observation.planet_id), observation.planet.iau_code])

    return highlights_dso_list, highlights_pos_list


def common_highlights_from_session_plan(session_plan):
    highlights_dso_list = []
    highlights_pos_list = []

    if session_plan and allow_view_session_plan(session_plan):
        for item in session_plan.session_plan_items:
            if item.item_type == SessionPlanItemType.DSO:
                highlights_dso_list.append(item.deepsky_object)
            elif item.item_type == SessionPlanItemType.DBL_STAR:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id), item.double_star.get_common_name()])
            elif item.item_type == SessionPlanItemType.COMET:
                highlights_pos_list.append([item.ra, item.dec, CHART_COMET_PREFIX + str(item.comet_id), item.comet.designation])
            elif item.item_type == SessionPlanItemType.MINOR_PLANET:
                highlights_pos_list.append([item.ra, item.dec, CHART_MINOR_PLANET_PREFIX + str(item.minor_planet_id), item.minor_planet.designation])
            elif item.item_type == SessionPlanItemType.PLANET:
                highlights_pos_list.append([item.ra, item.dec, CHART_PLANET_PREFIX + str(item.planet_id), item.planet.iau_code])
    return highlights_dso_list, highlights_pos_list


def create_hightlights_lists():
    highlights_dso_list = None
    highlights_pos_list = None

    back = request.args.get('back')
    back_id = request.args.get('back_id')

    if back == 'dso_list' and back_id is not None:
        dso_list = DsoList.query.filter_by(id=back_id).first()
        if dso_list:
            highlights_dso_list = [x.deepsky_object for x in dso_list.dso_list_items if dso_list]
    elif back == 'dbl_star_list' and back_id is not None:
        double_star_list = DoubleStarList.query.filter_by(id=back_id).first()
        if double_star_list:
            highlights_pos_list = [(x.double_star.ra_first, x.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(x.double_star.id),
                                    x.double_star.get_common_name()) for x in double_star_list.double_star_list_items if double_star_list]
    elif back == 'wishlist' and current_user.is_authenticated:
        wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
        highlights_dso_list, highlights_pos_list = common_highlights_from_wishlist_items(wish_list.wish_list_items if wish_list else None)
    elif back == 'session_plan':
        session_plan = SessionPlan.query.filter_by(id=back_id).first()
        highlights_dso_list, highlights_pos_list = common_highlights_from_session_plan(session_plan)
    elif back == 'observation':
        observing_session = ObservingSession.query.filter_by(id=back_id).first()
        if observing_session and (observing_session.is_public or observing_session.user_id == current_user.id):
            highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)
    elif back == 'observed_list' and current_user.is_authenticated:
        observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
        highlights_dso_list, highlights_pos_list = common_highlights_from_observed_list_items(observed_list.observed_list_items if observed_list else None)
    elif back == 'running_plan' and back_id is not None:
        observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
        if observation_plan_run and allow_view_session_plan(observation_plan_run.session_plan):
            highlights_dso_list = []
            for item in observation_plan_run.session_plan.session_plan_items:
                if item.deepsky_object:
                    highlights_dso_list.append(item.deepsky_object)

    return highlights_dso_list, highlights_pos_list


def create_observed_dso_ids_list():
    back = request.args.get('back')
    back_id = request.args.get('back_id')

    if back == 'dso_list' and back_id is not None:
        return find_dso_list_observed(back_id)
    if back == 'wishlist' and current_user.is_authenticated:
        wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
        return find_wish_list_observed(wish_list)
    return None


def find_wish_list_observed(wish_list):
    if wish_list:
        observed_query = db.session.query(WishListItem.dso_id) \
            .filter(WishListItem.wish_list_id == wish_list.id) \
            .join(WishListItem.deepsky_object)
        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedList) \
            .filter(ObservedList.user_id == current_user.id) \
            .filter(ObservedListItem.dso_id.is_not(None))
        observed_query = observed_query.filter(or_(WishListItem.dso_id.in_(observed_subquery), DeepskyObject.master_id.in_(observed_subquery)))
        return set(r[0] for r in observed_query.all())
    return None

def find_dso_list_observed(dso_list_id):
    if not current_user.is_anonymous:
        observed_query = db.session.query(DsoListItem.dso_id) \
            .filter(DsoListItem.dso_list_id == dso_list_id) \
            .join(DsoListItem.deepsky_object)
        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedList) \
            .filter(ObservedList.user_id == current_user.id) \
            .filter(ObservedListItem.dso_id.is_not(None))
        observed_query = observed_query.filter(or_(DsoListItem.dso_id.in_(observed_subquery), DeepskyObject.master_id.in_(observed_subquery)))
        return set(r[0] for r in observed_query.all())
    return None
