from time import time

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app.commons.search_sky_object_utils import (
    search_dso,
    search_double_star,
    search_comet,
    search_minor_planet,
    search_planet,
    search_planet_moon
)
from app.commons.minor_planet_utils import find_mpc_minor_planet
from app.commons.comet_utils import find_mpc_comet
from app.commons.solar_system_chart_utils import create_planet_moon_obj

from app.models import (
    ObservationTargetType,
)


def parse_observation_targets(targets):
    not_found = []
    dsos = []
    planet = None
    planet_moon = None
    comet = None
    minor_planet = None
    double_star = None

    targets = targets.strip()

    planet = search_planet(targets)
    if planet:
        return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

    planet_moon = search_planet_moon(targets)
    if planet_moon:
        return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

    comet = search_comet(targets)
    if comet:
        return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

    minor_planet = search_minor_planet(targets)
    if minor_planet:
        return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

    target_names = targets.split(',')
    for target_name in target_names:
        dso = search_dso(target_name)
        if dso:
            dsos.append(dso)
            continue
        not_found.append(target_name)

    if len(dsos) > 0:
        return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

    # double star as a last since there is slow query (.. like '%name%')
    double_star = search_double_star(targets, number_search=False)

    if double_star:
        not_found = []
    return dsos, double_star, planet, planet_moon, comet, minor_planet, not_found

def set_observation_targets(observation, targets):
    observation.deepsky_objects = []
    observation.double_star_id = None
    dsos, double_star, planet, planet_moon, comet, minor_planet, not_found = parse_observation_targets(targets)
    if double_star:
        observation.double_star_id = double_star.id
        observation.target_type = ObservationTargetType.DBL_STAR
    elif planet:
        observation.planet_id = planet.id
        observation.target_type = ObservationTargetType.PLANET

        ts = load.timescale(builtin=True)
        eph = load('de421.bsp')
        earth = eph['earth']

        dt = observation.date_from
        t = ts.utc(dt.year, dt.month, dt.day)
        planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()

        observation.ra = planet_ra_ang.radians
        observation.dec = planet_dec_ang.radians
    elif planet_moon:
        observation.planet_moon_id = planet_moon.id
        observation.target_type = ObservationTargetType.PLANET_MOON

        plm_obj = create_planet_moon_obj(planet_moon.name)

        observation.ra = plm_obj.ra
        observation.dec = plm_obj.dec
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
    elif minor_planet:
        observation.minor_planet_id = minor_planet.id
        observation.target_type = ObservationTargetType.M_PLANET

        ts = load.timescale(builtin=True)
        eph = load('de421.bsp')
        sun, earth = eph['sun'], eph['earth']

        mpc_minor_planet = find_mpc_minor_planet(minor_planet.int_designation)
        c = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

        dt = observation.date_from
        t = ts.utc(dt.year, dt.month, dt.day)
        minor_planet_ra_ang, minor_planet_dec_ang, distance = earth.at(t).observe(c).radec()
        observation.ra = minor_planet_ra_ang.radians
        observation.dec = minor_planet_dec_ang.radians
    elif dsos:
        for dso in dsos:
            observation.deepsky_objects.append(dso)
        observation.target_type = ObservationTargetType.DSO
