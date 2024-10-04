from skyfield.api import load

from math import asin

import datetime as dt_module
import fchart3

from app.models import (
    BODY_KEY_DICT,
)

utc = dt_module.timezone.utc


PLANET_RADIUS_DICT = {
    'sun': 696340,
    'moon': 1737.1,
    'mercury': 2439.7,
    'venus': 6051.8,
    'mars': 3389.5,
    'jupiter': 69911,
    'saturn': 58232,
    'uranus': 25362,
    'neptune': 24622,
    'pluto': 1188.3
}

AU_TO_KM = 149597870.7

def get_mpc_planet_position(planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))

    ra_ang, dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    return ra_ang, dec_ang


def create_solar_system_body_obj(eph, body_enum, t=None):
    if body_enum == fchart3.SolarSystemBody.EARTH:
        return None

    if t is None:
        ts = load.timescale(builtin=True)
        t = ts.now()

    body_name = body_enum.name.lower()
    if body_name in ['sun', 'moon']:
        body = eph[body_name]
    else:
        body = eph[BODY_KEY_DICT[body_name]]

    earth = eph['earth'].at(t)
    astrometric = earth.observe(body)
    ra_ang, dec_ang, distance = astrometric.radec()

    ra = ra_ang.radians
    dec = dec_ang.radians

    distance_km = distance.au * AU_TO_KM

    physical_radius_km = PLANET_RADIUS_DICT.get(body_name)

    if physical_radius_km and distance_km > physical_radius_km:
        angular_radius = asin(physical_radius_km / distance_km)
    else:
        angular_radius = 0

    if body_enum != fchart3.SolarSystemBody.SUN:
        p = eph['earth'].at(t).observe(body)
        phase_angle = p.phase_angle(eph['sun']).radians
    else:
        phase_angle = None

    return fchart3.SolarSystemBodyObject(body_enum, ra, dec, angular_radius, phase_angle, distance_km)


def create_planet_moon_obj(eph, planet, moon_name, mag, t=None):
    if t is None:
        ts = load.timescale(builtin=True)
        t = ts.now()

    pl_moon = eph[moon_name.lower()]
    earth = eph['earth'].at(t)
    astrometric = earth.observe(pl_moon)
    ra_ang, dec_ang, distance = astrometric.radec()

    distance_km = distance.au * AU_TO_KM

    return fchart3.PlanetMoonObject(planet, moon_name, ra_ang.radians, dec_ang.radians, mag, distance_km)
