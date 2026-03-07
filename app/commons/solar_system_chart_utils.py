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
_SKYFIELD_TS = load.timescale(builtin=True)
_EPHEMERIS_CACHE = {}


def _get_ephemeris(url):
    """Get cached ephemeris to avoid opening too many files."""
    if url not in _EPHEMERIS_CACHE:
        _EPHEMERIS_CACHE[url] = load(url)
    return _EPHEMERIS_CACHE[url]

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

# IAU 2015 North Pole coordinates (RA, Dec) in radians
# Reference: Report of the IAU Working Group on Cartographic Coordinates
PLANET_NORTH_POLE = {
    'mercury': [math.radians(281.01), math.radians(61.45)],
    'venus': [math.radians(272.76), math.radians(67.16)],
    'mars': [math.radians(317.68), math.radians(52.89)],
    'jupiter': [math.radians(268.06), math.radians(64.50)],
    'saturn': [math.radians(40.589), math.radians(83.537)],
    'uranus': [math.radians(257.31), math.radians(-15.18)],
    'neptune': [math.radians(299.36), math.radians(43.46)],
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

# Moons that can cast observable shadows on their parent planet
SHADOW_CASTING_MOONS = {'io', 'europa', 'ganymede', 'callisto', 'titan'}

YEAR_DAYS = 365.25
AU_TO_KM = 149597870.7
SATURN_POLE = np.array([0.08547883, 0.07323576, 0.99364475])
C_AU_PER_DAY = 173.1446326846693
JD_UNIX_EPOCH = 2440587.5

# Legacy skytechx defaults used to align Jupiter texture/GRS.
JUPITER_GRS_LON0_DEG = 236.0
JUPITER_GRS_YEAR_DRIFT_DEG = 16.6
JUPITER_GRS_REF_JD = 2457388.5
JUPITER_GRS_YEAR_DAYS = 365.256

# IAU rotation model (base_rad, rate_rad_per_century) used for sub-Earth latitude
_POLE_RA_DEC_RATES = {
    'sun': ((math.radians(286.13), 0.0), (math.radians(63.87), 0.0)),
    'mercury': ((math.radians(281.0097), -math.radians(0.0328)),
                (math.radians(61.4143), -math.radians(0.0049))),
    'venus': ((math.radians(272.76), 0.0), (math.radians(67.16), 0.0)),
    'mars': ((math.radians(317.6814), -math.radians(0.1061)),
             (math.radians(52.8865), -math.radians(0.0609))),
    'jupiter': ((math.radians(268.056595), -math.radians(0.006499)),
                (math.radians(64.4953), math.radians(0.002413))),
    'saturn': ((math.radians(40.5954), -math.radians(0.0577)),
               (math.radians(83.5380), -math.radians(0.0066))),
    'uranus': ((math.radians(257.311), 0.0), (-math.radians(15.175), 0.0)),
    'neptune': ((math.radians(299.36), 0.0), (math.radians(43.46), 0.0)),
}

_ROTATION_MUL = {
    'sun': -1.0,
    'mercury': 1.0,
    'venus': -1.0,
    'mars': 1.0,
    'jupiter': 1.0,
    'saturn': 1.0,
    'uranus': -1.0,
    'neptune': 1.0,
    'moon': -1.0,  # lunar texture convention matches sun/venus sign in renderer
}


def _normalize_angle_rad(angle):
    return angle % (2.0 * math.pi)


def _datetime_to_jd_utc(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    else:
        dt = dt.astimezone(utc)
    return dt.timestamp() / 86400.0 + JD_UNIX_EPOCH


def get_jupiter_grs_offset_rad(dt: datetime) -> float:
    """
    Jupiter GRS longitude offset in radians, matching legacy drift model.
    """
    jd = _datetime_to_jd_utc(dt)
    years = (jd - JUPITER_GRS_REF_JD) / JUPITER_GRS_YEAR_DAYS
    lon_deg = JUPITER_GRS_LON0_DEG + JUPITER_GRS_YEAR_DRIFT_DEG * years
    return math.radians(lon_deg % 360.0)


def _planet_pole_ra_dec(body_name, jd_tdb):
    if body_name == 'moon':
        d = jd_tdb - 2451545.0
        t_cent = d / 36525.0
        e1 = math.radians(125.045 - 0.0529921 * d)
        pole_ra = math.radians(269.9949 + 0.0031 * t_cent - 3.8787 * math.sin(e1))
        pole_dec = math.radians(66.5392 + 0.0130 * t_cent + 1.5419 * math.cos(e1))
        return pole_ra, pole_dec

    pole_entry = _POLE_RA_DEC_RATES.get(body_name)
    if not pole_entry:
        return None, None
    t_cent = (jd_tdb - 2451545.0) / 36525.0
    (ra0, ra_rate), (dec0, dec_rate) = pole_entry
    return ra0 + ra_rate * t_cent, dec0 + dec_rate * t_cent


def _rotation_w_deg(body_name, jd_tdb_minus_light_days):
    d = jd_tdb_minus_light_days - 2451545.0
    if body_name == 'sun':
        return 84.176 + 14.1844 * d
    if body_name == 'mercury':
        m1 = 174.791086 + 4.092335 * d
        return 329.5469 + 6.1385025 * d + 0.00993822 * math.sin(math.radians(m1))
    if body_name == 'venus':
        return 160.20 - 1.4813688 * d
    if body_name == 'mars':
        return 176.630 + 350.89198226 * d
    if body_name == 'jupiter':
        return 43.3 + 870.270 * d  # System II (tropické zóny, kde je GRS)
    if body_name == 'saturn':
        return 227.2037 + 844.3 * d
    if body_name == 'uranus':
        return 203.81 - 501.1600928 * d
    if body_name == 'neptune':
        return 253.18 + 536.3128492 * d
    if body_name == 'moon':
        # IAU lunar prime meridian (main term + dominant periodic correction).
        e1 = math.radians(125.045 - 0.0529921 * d)
        return 38.3213 + 13.17635815 * d + 3.5610 * math.sin(e1)
    return None


def _planetographic_orientation(body_name, t, ra, dec, astrometric):
    pole_ra, pole_dec = _planet_pole_ra_dec(body_name, t.tdb)
    if pole_ra is None or pole_dec is None:
        return None, None

    sd = -math.sin(pole_dec) * math.sin(dec)
    sd -= math.cos(pole_dec) * math.cos(dec) * math.cos(pole_ra - ra)
    sd = max(-1.0, min(1.0, sd))
    sub_earth_lat = math.atan2(sd, math.sqrt(max(0.0, 1.0 - sd * sd)))

    w_deg = _rotation_w_deg(body_name, t.tdb - float(astrometric.light_time))
    mul = _ROTATION_MUL.get(body_name)
    if w_deg is None or mul is None:
        return None, sub_earth_lat

    w = math.radians(w_deg % 360.0)
    lon_term = math.atan2(
        math.sin(pole_dec) * math.cos(dec) * math.cos(pole_ra - ra)
        - math.sin(dec) * math.cos(pole_dec),
        math.cos(dec) * math.sin(pole_ra - ra),
    )
    central_meridian = _normalize_angle_rad((w - lon_term) * mul)
    return central_meridian, sub_earth_lat


def get_planet_texture_orientation(body_name, dt, ra, dec, distance_km):
    if body_name not in _POLE_RA_DEC_RATES and body_name != 'moon':
        return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    t = _SKYFIELD_TS.from_datetime(dt)

    pole_ra, pole_dec = _planet_pole_ra_dec(body_name, t.tdb)
    if pole_ra is None or pole_dec is None:
        return None, None

    sd = -math.sin(pole_dec) * math.sin(dec)
    sd -= math.cos(pole_dec) * math.cos(dec) * math.cos(pole_ra - ra)
    sd = max(-1.0, min(1.0, sd))
    sub_earth_lat = math.atan2(sd, math.sqrt(max(0.0, 1.0 - sd * sd)))

    if distance_km is None:
        return None, sub_earth_lat

    light_days = (distance_km / AU_TO_KM) / C_AU_PER_DAY
    w_deg = _rotation_w_deg(body_name, t.tdb - light_days)
    mul = _ROTATION_MUL.get(body_name)
    if w_deg is None or mul is None:
        return None, sub_earth_lat

    w = math.radians(w_deg % 360.0)
    lon_term = math.atan2(
        math.sin(pole_dec) * math.cos(dec) * math.cos(pole_ra - ra)
        - math.sin(dec) * math.cos(pole_dec),
        math.cos(dec) * math.sin(pole_ra - ra),
    )
    central_meridian = _normalize_angle_rad((w - lon_term) * mul)
    return central_meridian, sub_earth_lat


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
    eph = _get_ephemeris('de421.bsp')
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

    eph = _get_ephemeris('de421.bsp')

    for body_enum in fchart3.SolarSystemBody:
        if body_enum != fchart3.SolarSystemBody.EARTH and body_enum != fchart3.SolarSystemBody.MOON:
            solsys_body_obj = create_solar_system_body_obj(eph, body_enum, t)
            sls_bodies.append(solsys_body_obj)

    return sls_bodies


@lru_cache(maxsize=100)
def _get_moon_cached(dt: datetime, observer_lat=None, observer_lon=None, observer_elevation=0.0):
    ts = load.timescale(builtin=True)
    t = ts.from_datetime(dt.replace(tzinfo=utc))

    eph = _get_ephemeris('de421.bsp')

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
            eph = _get_ephemeris(eph_url)
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
                    eph = _get_ephemeris(eph_url)
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
        pole_ra, pole_dec = north_pole[0], north_pole[1]
        north_pole_pa = get_north_pole_pa(pole_ra, pole_dec, ra, dec)
    elif body_name == 'moon':
        pole_ra, pole_dec = _planet_pole_ra_dec('moon', t.tdb)
        north_pole_pa = get_north_pole_pa(pole_ra, pole_dec, ra, dec)
    else:
        north_pole_pa = None

    central_meridian = None
    sub_earth_lat = None
    if body_name in _POLE_RA_DEC_RATES or body_name == 'moon':
        central_meridian, sub_earth_lat = _planetographic_orientation(
            body_name, t, ra, dec, astrometric
        )

    if body_enum == fchart3.SolarSystemBody.SUN:
        mag = -26.7
    elif body_enum == fchart3.SolarSystemBody.MOON:
        mag = -12.0
    elif body_enum == fchart3.SolarSystemBody.PLUTO:
        mag = 14.5
    else:
        mag = planetary_magnitude(astrometric)

    body_obj = fchart3.SolarSystemBodyObject(
        body_enum,
        ra,
        dec,
        north_pole_pa,
        angular_radius,
        mag,
        phase_angle,
        distance_km,
        ring_tilt,
    )
    if hasattr(body_obj, 'central_meridian'):
        body_obj.central_meridian = central_meridian
    if hasattr(body_obj, 'sub_earth_lat'):
        body_obj.sub_earth_lat = sub_earth_lat
    return body_obj


def _sphere_intersection(ray_direction, sphere_pos, sphere_radius):
    """
    Test ray-sphere intersection.
    Ray starts at origin (Sun) with given direction.

    Args:
        ray_direction: direction vector (numpy array)
        sphere_pos: position of sphere center (numpy array)
        sphere_radius: radius of sphere

    Returns:
        (hit: bool, hit_point: array or None)
    """
    mag_d = np.linalg.norm(ray_direction)

    if mag_d <= 0.0:
        int_dist = np.linalg.norm(sphere_pos)
        return (int_dist < sphere_radius, None)

    dn = ray_direction / mag_d

    w_dist = np.dot(dn, sphere_pos)

    if w_dist <= -sphere_radius:
        return (False, None)

    if w_dist >= mag_d + sphere_radius:
        return (False, None)

    closest_point = dn * w_dist

    dist = np.linalg.norm(closest_point - sphere_pos)

    if dist < sphere_radius:
        hit_point = w_dist * dn
        return (True, hit_point)

    return (False, None)


def _calculate_moon_shadow_state(moon_helio, planet_helio, planet_radius_au):
    """
    Calculate moon shadow state.

    Args:
        moon_helio: heliocentric position of moon (numpy array)
        planet_helio: heliocentric position of planet (numpy array)
        planet_radius_au: radius of planet in AU

    Returns:
        (is_in_light: bool, is_throwing_shadow: bool, hit_point: array or None)
    """
    mn = moon_helio * 2.0

    plr = np.dot(planet_helio, planet_helio)
    sar = np.dot(moon_helio, moon_helio)

    hit, hit_point = _sphere_intersection(mn, planet_helio, planet_radius_au)

    if hit and sar > plr:
        return (False, False, None)
    elif hit:
        return (True, True, hit_point)

    return (True, False, None)


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

    is_in_light = True
    is_throwing_shadow = False
    shadow_ra = None
    shadow_dec = None

    planet_name_lower = planet.name.lower()
    planet_radius_km = PLANET_DATA.get(planet_name_lower, [None])[0]
    moon_name_lower = moon_name.lower()

    # Only calculate shadows for moons that can cast observable shadows
    if planet_radius_km is not None and moon_name_lower in SHADOW_CASTING_MOONS:
        planet_radius_au = planet_radius_km / AU_TO_KM

        planet_barycenter_name = planet_name_lower + ' barycenter'
        try:
            planet_body = eph[planet_barycenter_name]
        except KeyError:
            planet_body = None

        if planet_body is not None:
            moon_helio = pl_moon.at(t).position.au
            planet_helio = planet_body.at(t).position.au

            is_in_light, is_throwing_shadow, hit_point = _calculate_moon_shadow_state(
                moon_helio, planet_helio, planet_radius_au
            )

            if is_throwing_shadow and hit_point is not None:
                earth_pos = eph['earth'].at(t).position.au
                geo_hit = hit_point - earth_pos
                shadow_ra = math.atan2(geo_hit[1], geo_hit[0])
                shadow_dec = math.atan2(geo_hit[2], math.sqrt(geo_hit[0]**2 + geo_hit[1]**2))

    return fchart3.PlanetMoonObject(
        planet, moon_name, ra_ang.radians, dec_ang.radians, mag, color, distance_earth_km,
        is_in_light, is_throwing_shadow, shadow_ra, shadow_dec
    )


def get_planet_orbital_period(planet):
    return PLANET_DATA[planet][1]


def get_planet_synodic_period(planet):
    return PLANET_DATA[planet][2]
