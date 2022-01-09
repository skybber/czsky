from app.commons.coordinates import parse_latlon

from app.commons.openastronomylog import angleUnit, OalangleType, OalnonNegativeAngleType, OalequPosType, OalsurfaceBrightnessType
from app.commons.openastronomylog import OalobserverType, OalobserversType
from app.commons.openastronomylog import OalsiteType, OalsitesType
from app.commons.openastronomylog import Oalobservations, OalobservationType
from app.commons.openastronomylog import OaltargetsType, OalobservationTargetType


def create_oal_observations(user, session_plans):
    # Observers
    oal_observer = OalobserverType(id='usr_{}'.format(user.id),
                                   name=user.get_first_name(),
                                   surname=user.get_last_name(),
                                   contact=[user.email],
                                   )
    oal_observers = OalobserversType(observer=[oal_observer])

    # Sites
    oal_sites = OalsitesType()
    proc_locations = set()
    for session_plan in session_plans:
        location = session_plan.location
        if location:
            if location.id in proc_locations:
                continue
            proc_locations.add(location.id)
            oal_site = OalsiteType(id='site_{}'.format(location.id), name=location.name,
                                   longitude=_get_oal_angle(angleUnit.DEG, location.longitude), latitude=_get_oal_angle(angleUnit.DEG, location.latitude),
                                   elevation=(location.elevation if location.elevation and location.elevation != 0 else None),
                                   timezone=location.timezone, code=location.iau_code)
        else:
            lat, lon = parse_latlon(session_plan.location_position)
            oal_site = OalsiteType(id='site_adhoc_{}'.format(session_plan.id), name=None,
                                   longitude=_get_oal_angle(angleUnit.DEG, lon), latitude=_get_oal_angle(angleUnit.DEG, lat),
                                   elevation=None, timezone=None, code=None)
        oal_sites.add_site(oal_site)

    # Targets
    oal_targets = OaltargetsType()
    proc_targets = set()
    for session_plan in session_plans:
        for session_plan_item in session_plan.session_plan_items:
            dso = session_plan_item.deepskyObject
            if dso.id in proc_targets:
                continue
            proc_targets.add(dso.id)
            oal_obs_target = OalobservationTargetType(id='_{}'.format(dso.id), datasource='CzSky', observer=None,
                                                      name=dso.name, alias=None, position=_get_oal_equ_pos(dso.ra, dso.dec),
                                                      constellation=dso.get_constellation_iau_code(),
                                                      notes=None, extensiontype_=None)
            oal_targets.add_target(oal_obs_target)

    oal_observations = Oalobservations(observers=oal_observers, sites=oal_sites, sessions=None, targets=oal_targets,
                                       scopes=None, eyepieces=None, lenses=None, filters=None,
                                       images=None, observation=None)

    return oal_observations


def _get_oal_angle(unit, angle):
    return OalangleType(unit=unit, valueOf_=angle)


def _get_oal_non_neg_angle(unit, angle):
    return OalnonNegativeAngleType(unit=unit, valueOf_=angle)


def _get_oal_equ_pos(ra, dec):
    return OalequPosType(ra=_get_oal_non_neg_angle(angleUnit.RAD, ra), dec=_get_oal_angle(angleUnit.RAD, dec))
