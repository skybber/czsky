from skyfield.api import load
from skyfield.magnitudelib import planetary_magnitude

import numpy as np
from math import asin, log10
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

        sls_bodies = []

        eph = load('de421.bsp')

        for body_enum in fchart3.SolarSystemBody:
            if body_enum != fchart3.SolarSystemBody.EARTH:
                solsys_body_obj = _create_solar_system_body_obj(eph, body_enum, t)
                sls_bodies.append(solsys_body_obj)

        solsys_bodies = sls_bodies
        solsys_last_updated = current_time

    return solsys_bodies


def get_planet_moons(maglim):
    global planet_moons, planet_moons_last_updated

    current_time = time()

    if planet_moons_last_updated is None or (current_time - planet_moons_last_updated) > 60:
        ts = load.timescale(builtin=True)
        t = ts.now()

        pl_moons = []

        eph_moons = {
            fchart3.SolarSystemBody.MARS: {
                MAR097_BSP: {
                    'Phobos': [11.8, (1.0, 0.919, 0.806)],
                    'Deimos': [12.89, (1.0, 0.93, 0.832)],
                },
            },
            fchart3.SolarSystemBody.JUPITER: {
                JUP365_BSP: {
                    'Io': [-1.68, (1.0, 0.885, 0.598)],
                    'Europa': [-1.41, (1.0, 0.968, 0.887)],
                    'Ganymede': [-2.09, (1.0, 0.962, 0.871)],
                    'Callisto': [-1.05, (1.0, 0.979, 0.897)],
                    'Amalthea': [7.4, (1.0, 0.627, 0.492)],
                },
                JUP344_BSP: {
                    'Himalia': [8.14, (1.0, 0.9, 0.75)],
                },
            },
            fchart3.SolarSystemBody.SATURN: {
                SAT_441_BSP: {
                    'Titan': [-1.28, (1.0, 0.807, 0.453)],
                    'Rhea': [0.1, (1.0, 0.981, 0.942)],
                    'Iapetus': [1.5, (1.0, 0.973, 0.948)],
                    'Enceladus': [2.1, (1.0, 0.998, 0.991)],
                    'Mimas': [3.3, (1.0, 0.983, 0.972)],
                    'Tethys': [0.6, (0.999, 1.0, 0.999)],
                    'Dione': [0.8, (1.0, 0.98, 0.966)],
                    'Phoebe': [6.89, (1.0, 0.9, 0.75)],
                    'Hyperion': [4.63, (1.0, 0.914, 0.835)],
                },
            },
            fchart3.SolarSystemBody.URANUS: {
                URA111_BSP: {
                    'Titania': [1.02, (1.0, 0.875, 0.779)],
                    'Oberon': [1.23, (1.0, 0.875, 0.798)],
                    'Umbriel': [2.1, (1.0, 0.956, 0.956)],
                    'Ariel': [1.45, (1.0, 0.849, 0.731)],
                    'Miranda': [3.6, (1.0, 0.902, 0.871)],
                },
            },
            fchart3.SolarSystemBody.NEPTUNE: {
                NEP097_BSP: {
                    'Triton': [-1.24, (0.961, 1.0, 0.819)],
                },
            },
        }

        for planet, url_moons in eph_moons.items():
            for eph_url, moons in url_moons.items():
                eph = load(eph_url)
                for moon_name, (abs_mag, color) in moons.items():
                    planet_moon_obj = _create_planet_moon_obj(eph, planet, moon_name, abs_mag, color, t)
                    pl_moons.append(planet_moon_obj)

        planet_moons = pl_moons

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

    if body_enum == fchart3.SolarSystemBody.SUN:
        mag = -26.7
    elif body_enum == fchart3.SolarSystemBody.MOON:
        mag = -12
    elif body_enum == fchart3.SolarSystemBody.PLUTO:
        mag = 14.5
    else:
        mag = planetary_magnitude(astrometric)

    return fchart3.SolarSystemBodyObject(body_enum, ra, dec, angular_radius, mag, phase_angle, distance_km, ring_tilt)


def _create_planet_moon_obj(eph, planet, moon_name, abs_mag, color, t=None):
    if t is None:
        ts = load.timescale(builtin=True)
        t = ts.now()

    pl_moon = eph[moon_name.lower()]
    earth = eph['earth'].at(t)
    sun = eph['sun'].at(t)

    astrometric_from_earth = earth.observe(pl_moon)
    ra_ang, dec_ang, distance = astrometric_from_earth.radec()

    astrometric_from_sun = sun.observe(pl_moon)
    distance_sun_au = astrometric_from_sun.distance().au

    distance_earth_au = distance.au
    distance_earth_km = distance.au * AU_TO_KM

    mag = abs_mag + 5 * log10(distance_sun_au * distance_earth_au)

    print('{} {}'.format(moon_name, mag))

    return fchart3.PlanetMoonObject(planet, moon_name, ra_ang.radians, dec_ang.radians, mag, color, distance_earth_km)
