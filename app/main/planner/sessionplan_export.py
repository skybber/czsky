import pytz
import datetime

from app.commons.coordinates import parse_latlon

from app.commons.oal_export_utils import get_oal_angle, get_oal_non_neg_angle, create_dso_observation_target

from app.commons.openastronomylog import angleUnit, OalangleType, OalnonNegativeAngleType, OalequPosType, OalsurfaceBrightnessType
from app.commons.openastronomylog import OalobserverType, OalobserversType
from app.commons.openastronomylog import OalsiteType, OalsitesType
from app.commons.openastronomylog import Oalobservations, OalobservationType
from app.commons.openastronomylog import OaltargetsType, OalobservationTargetType


def create_oal_observations_from_session_plan(user, session_plan):
    # Observers
    oal_observer = OalobserverType(id='usr_{}'.format(user.id),
                                   name=user.get_first_name(),
                                   surname=user.get_last_name(),
                                   contact=[user.email],
                                   )
    oal_observers = OalobserversType(observer=[oal_observer])

    # Sites
    oal_sites = OalsitesType()
    location = session_plan.location
    if location:
        tz_utc_offset = None
        if location.time_zone:
            tz_now = datetime.datetime.now(pytz.timezone(location.time_zone))
            tz_utc_offset = tz_now.utcoffset().total_seconds()/60
        oal_site = OalsiteType(id='site_{}'.format(location.id), name=location.name,
                               longitude=get_oal_angle(angleUnit.DEG, location.longitude), latitude=get_oal_angle(angleUnit.DEG, location.latitude),
                               elevation=(location.elevation if location.elevation and location.elevation != 0 else None),
                               timezone=tz_utc_offset, code=location.iau_code)
    else:
        lat, lon = parse_latlon(session_plan.location_position)
        oal_site = OalsiteType(id='site_adhoc_{}'.format(session_plan.id), name=None,
                               longitude=get_oal_angle(angleUnit.DEG, lon), latitude=get_oal_angle(angleUnit.DEG, lat),
                               elevation=None, timezone=None, code=None)
    oal_sites.add_site(oal_site)

    # Targets
    oal_targets = OaltargetsType()
    proc_targets = set()
    for session_plan_item in session_plan.session_plan_items:
        dso = session_plan_item.deepsky_object
        if dso.id in proc_targets:
            continue
        proc_targets.add(dso.id)
        oal_obs_target = create_dso_observation_target(dso)
        oal_targets.add_target(oal_obs_target)

    oal_observations = Oalobservations(observers=oal_observers, sites=oal_sites, sessions=None, targets=oal_targets,
                                       scopes=None, eyepieces=None, lenses=None, filters=None,
                                       images=None, observation=None)

    return oal_observations


def _get_oal_equ_pos(ra, dec):
    return OalequPosType(ra=get_oal_non_neg_angle(angleUnit.RAD, ra), dec=get_oal_angle(angleUnit.RAD, dec))
