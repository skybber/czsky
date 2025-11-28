import math
from functools import lru_cache
from datetime import datetime

from skyfield.api import load, Topos
from skyfield.magnitudelib import planetary_magnitude

import numpy as np

import datetime as dt_module
import fchart3

from app.models import (
    BODY_KEY_DICT,
)

MAR099S_BSP = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar099s.bsp"
JUP365_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/jup365.bsp'
JUP347_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/jup347.bsp'
SAT_441_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/sat441.bsp'
# TODO: URA is splitted now to ura184_part-1.bsp ... ura184_part-3.bsp
URA111_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/a_old_versions/ura111.bsp'
NEP097_BSP = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/nep097.bsp'


utc = dt_module.timezone.utc

PLANET_DATA = {
    'sun': [696340],
    'moon': [1737.1],
    'mercury': [2439.7, 87.97, 115.88],
    'venus': [6051.8, 224.70, 583.92],
    'mars': [3389.5, 686.98, 779.94],
    'jupiter': [69911, 4332.59, 398.88],
    'saturn': [58232, 10759.22, 378.09],
    'uranus': [25362, 30687.15, 369.66],
    'neptune': [24622, 60190.03, 367.49],
    'pluto': [1188.3, 90560.0, 366.73]
}

PLANET_NORTH_POLE = {
    'saturn': [math.radians(40.589), math.radians(83.537)]
}

PLANET_MOONS_DATA = {
    fchart3.SolarSystemBody.MARS: {
        MAR099S_BSP: {
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
        JUP347_BSP: {
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

YEAR_DAYS = 365.25
AU_TO_KM = 149597870.7
SATURN_POLE = np.array([0.08547883, 0.07323576, 0.99364475])


def get_north_pole_pa(ra, dec, obj_ra, obj_dec):
    """
    Calculate the North position angle
    Parameters:
        ra (float): North Pole Right Ascension in radians.
        dec (float): North Pole Declination in radians.
        obj_ra (float): Object Right Ascension in radians.
        obj_dec (float): Object Declination in radians.
    Returns:
        float: The adjusted PA within [0, 2*pi).
    """
    d1 = dec
    a1 = ra

    a5 = obj_ra
    d5 = obj_dec

    sp = math.cos(d1) * math.sin(a1 - a5)
    cp = math.sin(d1) * math.cos(d5)

    cp -= math.cos(d1) * math.sin(d5) * math.cos(a1 - a5)

    pa = math.atan2(sp, cp)
    pa = pa % (2 * math.pi)

    return pa


def get_mpc_planet_position(planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))

    ra_ang, dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    return ra_ang, dec_ang


def _normalize_to_60s(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    return dt.replace(second=0, microsecond=0)


@lru_cache(maxsize=100)
def _get_solsys_bodies_cached(dt: datetime):
    ts = load.timescale(builtin=True)
    t = ts.from_datetime(dt.replace(tzinfo=utc))

    sls_bodies = []

    eph = load('de421.bsp')

    for body_enum in fchart3.SolarSystemBody:
        if body_enum != fchart3.SolarSystemBody.EARTH and body_enum != fchart3.SolarSystemBody.MOON:
            solsys_body_obj = create_solar_system_body_obj(eph, body_enum, t)
            sls_bodies.append(solsys_body_obj)

    return sls_bodies


@lru_cache(maxsize=100)
def _get_moon_cached(dt: datetime, observer_lat=None, observer_lon=None, observer_elevation=0.0):
    ts = load.timescale(builtin=True)
    t = ts.from_datetime(dt.replace(tzinfo=utc))

    eph = load('de421.bsp')

    return create_solar_system_body_obj(eph, fchart3.SolarSystemBody.MOON, t, observer_lat, observer_lon, observer_elevation)


def get_solsys_bodies(datetime, observer_lat=None, observer_lon=None, observer_elevation=0.0):
    normalized_dt = _normalize_to_60s(datetime)
    result = []
    result.extend(_get_solsys_bodies_cached(normalized_dt))
    result.append(_get_moon_cached(normalized_dt, observer_lat, observer_lon, observer_elevation))
    return result


@lru_cache(maxsize=100)
def _get_planet_moons_cached(dt: datetime, maglim: float):

    ts = load.timescale(builtin=True)
    t = ts.from_datetime(dt.replace(tzinfo=utc))

    pl_moons = []

    for planet, url_moons in PLANET_MOONS_DATA.items():
        for eph_url, moons in url_moons.items():
            eph = load(eph_url)
            for moon_name, (abs_mag, color) in moons.items():
                planet_moon_obj = _create_planet_moon_obj(eph, planet, moon_name, abs_mag, color, t)
                pl_moons.append(planet_moon_obj)

    return [pl for pl in pl_moons if pl.mag <= maglim]


def get_planet_moons(dt: datetime, maglim: float):
    normalized_dt = _normalize_to_60s(dt)
    return _get_planet_moons_cached(normalized_dt, maglim)


def create_planet_moon_obj(moon_name, t=None):
    for planet, url_moons in PLANET_MOONS_DATA.items():
        for eph_url, moons in url_moons.items():
            for moon_name2, (abs_mag, color) in moons.items():
                if moon_name2.lower() == moon_name.lower():
                    eph = load(eph_url)
                    return _create_planet_moon_obj(eph, planet, moon_name, abs_mag, color, t)
    return None


def create_solar_system_body_obj(eph,
                                 body_enum,
                                 t=None,
                                 observer_lat=None,
                                 observer_lon=None,
                                 observer_elevation=0.0):
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

    if (observer_lat is not None) and (observer_lon is not None):
        location = Topos(latitude_degrees=observer_lat,
                         longitude_degrees=observer_lon,
                         elevation_m=observer_elevation)
        observer = (eph['earth'] + location).at(t)
    else:
        observer = eph['earth'].at(t)

    astrometric = observer.observe(body)
    ra_ang, dec_ang, distance = astrometric.radec()

    ra = ra_ang.radians
    dec = dec_ang.radians
    distance_km = distance.au * AU_TO_KM

    physical_radius_km = PLANET_DATA.get(body_name, [None])[0]
    if physical_radius_km and distance_km > physical_radius_km:
        angular_radius = math.asin(physical_radius_km / distance_km)
    else:
        angular_radius = 0.0

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

    north_pole = PLANET_NORTH_POLE.get(body_name)
    if north_pole:
        north_pole_pa = get_north_pole_pa(north_pole[0], north_pole[1], ra, dec)
    else:
        north_pole_pa = None

    if body_enum == fchart3.SolarSystemBody.SUN:
        mag = -26.7
    elif body_enum == fchart3.SolarSystemBody.MOON:
        mag = -12.0
    elif body_enum == fchart3.SolarSystemBody.PLUTO:
        mag = 14.5
    else:
        mag = planetary_magnitude(astrometric)

    return fchart3.SolarSystemBodyObject(
        body_enum,
        ra,
        dec,
        north_pole_pa,
        angular_radius,
        mag,
        phase_angle,
        distance_km,
        ring_tilt
    )


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

    mag = abs_mag + 5 * math.log10(distance_sun_au * distance_earth_au)

    return fchart3.PlanetMoonObject(planet, moon_name, ra_ang.radians, dec_ang.radians, mag, color, distance_earth_km)


def get_planet_orbital_period(planet):
    return PLANET_DATA[planet][1]


def get_planet_synodic_period(planet):
    return PLANET_DATA[planet][2]
