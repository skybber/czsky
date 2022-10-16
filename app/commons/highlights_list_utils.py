from flask import (
    request,
)

from flask_login import current_user

from app.models import (
    DoubleStarList,
    DsoList,
    ObservingSession,
    ObservedList,
    ObsSessionPlanRun,
    ObservationTargetType,
    SessionPlan,
    WishList,
)

from app.commons.permission_utils import allow_view_session_plan
from .dso_utils import CHART_DOUBLE_STAR_PREFIX


def common_highlights_from_wishlist_items(wish_list_items):
    highlights_dso_list = []
    highlights_pos_list = []

    if wish_list_items:
        for item in wish_list_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id)])
    return highlights_dso_list, highlights_pos_list


def common_highlights_from_observed_list_items(observed_list_items):
    highlights_dso_list = []
    highlights_pos_list = []

    if observed_list_items:
        for item in observed_list_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id)])
    return highlights_dso_list, highlights_pos_list


def common_highlights_from_observing_session(observing_session):
    highlights_dso_list = []
    highlights_pos_list = []

    if observing_session:
        for observation in observing_session.observations:
            if observation.target_type == ObservationTargetType.DSO:
                highlights_dso_list.extend(observation.deepsky_objects)
            elif observation.target_type == ObservationTargetType.DBL_STAR:
                highlights_pos_list.append([observation.double_star.ra_first, observation.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(observation.double_star_id)])
            elif observation.target_type == ObservationTargetType.COMET:
                highlights_pos_list.append([observation.ra, observation.dec, observation.comet.designation])
            elif observation.target_type == ObservationTargetType.M_PLANET:
                highlights_pos_list.append([observation.ra, observation.dec, observation.minor_planet.designation])
            elif observation.target_type == ObservationTargetType.PLANET:
                highlights_pos_list.append([observation.ra, observation.dec, observation.planet.get_localized_name()])

    return highlights_dso_list, highlights_pos_list


def common_highlights_from_session_plan(session_plan):
    highlights_dso_list = []
    highlights_pos_list = []

    if session_plan and allow_view_session_plan(session_plan):
        for item in session_plan.session_plan_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id)])
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
    elif back == 'double_star_list' and back_id is not None:
        double_star_list = DoubleStarList.query.filter_by(id=back_id).first()
        if double_star_list:
            highlights_pos_list = [(x.double_star.ra_first, x.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(x.double_star.id)) for x in double_star_list.double_star_list_items if double_star_list]
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
            highlights_dso_list = [x.deepsky_object for x in observation_plan_run.session_plan.session_plan_items]

    return highlights_dso_list, highlights_pos_list
