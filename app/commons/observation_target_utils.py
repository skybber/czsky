from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app.commons.dso_utils import normalize_dso_name
from app.commons.search_sky_object_utils import normalize_double_star_name, search_dso, search_double_star, search_comet

from app.models import (
    DeepskyObject,
    DoubleStar,
    ObservationTargetType,
)

from app.main.solarsystem.comet_views import find_mpc_comet


def parse_observation_targets(targets):
    not_found = []
    dsos = []
    comet = None
    double_star = search_double_star(targets, number_search=False)

    if double_star:
        return dsos, double_star, comet, not_found

    comet = search_comet(targets)
    if comet:
        return dsos, double_star, comet, not_found

    target_names = targets.split(',')
    for target_name in target_names:
        dso = search_dso(target_name)
        if dso:
            dsos.append(dso)
            continue
        not_found.append(target_name)

    return dsos, double_star, comet, not_found


def set_observation_targets(observation, targets):
    observation.deepsky_objects = []
    observation.double_star_id = None
    dsos, double_star, comet, not_found = parse_observation_targets(targets)
    if double_star:
        observation.double_star_id = double_star.id
        observation.target_type = ObservationTargetType.DBL_STAR
    elif comet:
        observation.comet_id = comet.id
        observation.target_type = ObservationTargetType.COMET

        mpc_comet = find_mpc_comet(comet.comet_id)
        ts = load.timescale(builtin=True)
        eph = load('de421.bsp')
        sun, earth = eph['sun'], eph['earth']
        c = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)

        dt = observation.date_from
        t = ts.utc(dt.year, dt.month, dt.day)
        comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
        observation.ra = comet_ra_ang.radians
        observation.dec = comet_dec_ang.radians
    elif dsos:
        for dso in dsos:
            observation.deepsky_objects.append(dso)
        observation.target_type = ObservationTargetType.DSO
