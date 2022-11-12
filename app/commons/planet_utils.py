from skyfield.api import load

import datetime as dt_module

utc = dt_module.timezone.utc


def get_mpc_planet_position(planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))

    ra_ang, dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    return ra_ang, dec_ang
