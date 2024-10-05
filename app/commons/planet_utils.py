from skyfield.api import load

import numpy as np
from math import asin
from time import time

import datetime as dt_module
import fchart3

from app.models import (
    BODY_KEY_DICT,
)

MAR097_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar097.bsp'
JUP365_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/jup365.bsp'
JUP344_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/jup344.bsp'
SAT_441_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/sat441.bsp'
URA111_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/ura111.bsp'
NEP097_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/nep097.bsp'


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
SATURN_POLE = np.array([0.08547883, 0.07323576, 0.99364475])

solsys_bodies = None
solsys_last_updated = None

planet_moons = None
planet_moons_last_updated = None


def get_mpc_planet_position(planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))

    ra_ang, dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    return ra_ang, dec_ang


def get_solsys_bodies():
    global solsys_bodies, solsys_last_updated

    current_time = time()

    if solsys_last_updated is None or (current_time - solsys_last_updated) > 60:
        ts = load.timescale(builtin=True)
        t = ts.now()

        solsys_bodies = []

        eph = load('de421.bsp')

        for body_enum in fchart3.SolarSystemBody:
            if body_enum != fchart3.SolarSystemBody.EARTH:
                solsys_body_obj = _create_solar_system_body_obj(eph, body_enum, t)
                solsys_bodies.append(solsys_body_obj)

        solsys_last_updated = current_time

    return solsys_bodies


def get_planet_moons(maglim):
    global planet_moons, planet_moons_last_updated

    current_time = time()

    if planet_moons_last_updated is None or (current_time - planet_moons_last_updated) > 60:
        ts = load.timescale(builtin=True)
        t = ts.now()

        planet_moons = []

        eph_moons = {
            fchart3.SolarSystemBody.MARS: {
                MAR097_BSP: {
                    'Phobos': 12.0,
                    'Deimos': 12.5,
                },
            },
            fchart3.SolarSystemBody.JUPITER: {
                JUP365_BSP: {
                    'Io': 5.5,
                    'Europa': 5.6,
                    'Ganymede': 5.0,
                    'Callisto': 6.3,
                    'Amalthea': 14.2,
                },
                JUP344_BSP: {
                    'Himalia': 14.9,
                },
            },
            fchart3.SolarSystemBody.SATURN: {
                SAT_441_BSP: {
                    'Titan': 8.4,
                    'Rhea': 9.7,
                    'Iapetus': 11.13,
                    'Enceladus': 11.74,
                    'Mimas': 12.9,
                    'Tethys': 10.24,
                    'Dione': 10.44,
                    'Phoebe': 11.13,
                    'Hyperion': 14.27,
                },
            },
            fchart3.SolarSystemBody.URANUS: {
                URA111_BSP: {
                    'Titania': 13.9,
                    'Oberon': 14.1,
                    'Umbriel': 14.9,
                    'Ariel': 14.3,
                    'Miranda': 16.5,
                },
            },
            fchart3.SolarSystemBody.NEPTUNE: {
                NEP097_BSP: {
                    'Triton': 13.4,
                },
            },
        }

        for planet, url_moons in eph_moons.items():
            for eph_url, moons in url_moons.items():
                eph = load(eph_url)
                for moon_name, mag in moons.items():
                    planet_moon_obj = _create_planet_moon_obj(eph, planet, moon_name, mag, t)
                    planet_moons.append(planet_moon_obj)

    return [pl for pl in planet_moons if pl.mag <= maglim]


def _create_solar_system_body_obj(eph, body_enum, t=None):
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
        phase_angle = astrometric.phase_angle(eph['sun']).radians
    else:
        phase_angle = None

    if body_enum == fchart3.SolarSystemBody.SATURN:
        r_se = body.at(t).observe(eph['earth']).position.au
        r_se_unit = r_se / np.linalg.norm(r_se)
        ring_tilt = np.arcsin(np.dot(r_se_unit, SATURN_POLE))
    else:
        ring_tilt = None

    return fchart3.SolarSystemBodyObject(body_enum, ra, dec, angular_radius, phase_angle, distance_km, ring_tilt)


def _create_planet_moon_obj(eph, planet, moon_name, mag, t=None):
    if t is None:
        ts = load.timescale(builtin=True)
        t = ts.now()

    pl_moon = eph[moon_name.lower()]
    earth = eph['earth'].at(t)
    astrometric = earth.observe(pl_moon)
    ra_ang, dec_ang, distance = astrometric.radec()

    distance_km = distance.au * AU_TO_KM

    return fchart3.PlanetMoonObject(planet, moon_name, ra_ang.radians, dec_ang.radians, mag, distance_km)
