import numpy as np
from io import BytesIO

from datetime import datetime, timedelta
import datetime as dt_module

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from flask import (
    current_app,
)

from app.commons.comet_loader import import_update_comets

from app.models import (
    Comet,
    CometObservation,
    Constellation,
)

utc = dt_module.timezone.utc

all_minor_planets = None
all_comets = None
all_comets_expiration = datetime.now() + timedelta(days=1)


def get_mag_coma_from_observations(observs):
    mag, coma_diameter = None, None
    if len(observs) > 0:
        n = 1
        mag = observs[0].mag
        coma_diameter = observs[0].coma_diameter
        first_dt = observs[0].date
        for o in observs[1:5]:
            if (first_dt - o.date).days > 2:
                break
            n += 1
            mag += o.mag
            if o.coma_diameter is not None:
                coma_diameter = (coma_diameter + o.coma_diameter) if coma_diameter is not None else o.coma_diameter
        if mag is not None:
            mag = mag / n
        if coma_diameter is not None:
            coma_diameter = coma_diameter / n

    return mag, coma_diameter


def get_all_comets():
    global all_comets
    global all_comets_expiration
    now = datetime.now()
    if all_comets is None or now > all_comets_expiration:
        all_comets_expiration = now + timedelta(days=1)
        with load.open(mpc.COMET_URL, reload=True) as f:
            # fix problem in coma in CometEls.txt
            lines = f.readlines()
            s = ''
            for line in lines:
                s += line.decode('ascii').replace(',', ' ')
            sio = BytesIO(s.encode('ascii'))
            # end of fix
            all_comets = mpc.load_comets_dataframe_slow(sio)
            all_comets = (all_comets.sort_values('reference')
                          .groupby('designation', as_index=False).last()
                          .set_index('designation', drop=False))
            all_comets['comet_id'] = np.where(all_comets['designation_packed'].isnull(), all_comets['designation'], all_comets['designation_packed'])
            all_comets['comet_id'] = all_comets['comet_id'].str.replace('/', '')
            all_comets['comet_id'] = all_comets['comet_id'].str.replace(' ', '')

            import_update_comets(all_comets, False)

        for comet in Comet.query.filter_by().all():
            after = datetime.today() - timedelta(days=31)
            mag, coma_diameter = comet.eval_mag, None
            real_mag = False
            observs = CometObservation.query.filter_by(comet_id=comet.id) \
                                      .filter(CometObservation.date >= after) \
                                      .order_by(CometObservation.date.desc()).all()[:5]

            comet_id = comet.comet_id
            if len(observs) > 0:
                mag, coma_diameter = get_mag_coma_from_observations(observs)
                current_app.logger.info('Setup comet mag from COBS comet={} mag={} coma_diameter={}'.format(comet_id, mag, coma_diameter))
                real_mag = True
            try:
                all_comets.loc[all_comets['comet_id'] == comet_id, 'mag'] = float('{:.1f}'.format(mag)) if mag else None
                all_comets.loc[all_comets['comet_id'] == comet_id, 'coma_diameter'] = '{:.1f}\''.format(coma_diameter) if coma_diameter else '-'
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_ra'] = comet.cur_ra_str_short()
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_dec'] = comet.cur_dec_str_short()
                constell = Constellation.get_constellation_by_id(comet.cur_constell_id)
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_constell'] = constell.iau_code if constell is not None else ''
                all_comets.loc[all_comets['comet_id'] == comet_id, 'real_mag'] = real_mag
            except Exception:
                pass

    return all_comets


def find_mpc_comet(comet_id):
    all_comets = get_all_comets()
    c = all_comets.loc[all_comets['comet_id'] == comet_id]
    return c.iloc[0] if len(c) > 0 else None


def get_mpc_comet_position(mpc_comet, dt):
    ts = load.timescale(builtin=True)
    t = ts.from_datetime(dt.replace(tzinfo=utc))
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    c = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)

    comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
    return comet_ra_ang, comet_dec_ang


def get_mpc_minor_planets():
    global all_minor_planets
    if all_minor_planets is None:
        with load.open('data/MPCORB.9999.DAT') as f:
            all_minor_planets = mpc.load_mpcorb_dataframe(f)
            bad_orbits = all_minor_planets.semimajor_axis_au.isnull()
            all_minor_planets = all_minor_planets[~bad_orbits]
            all_minor_planets['minor_planet_id'] = all_minor_planets['designation_packed']
    return all_minor_planets


def find_mpc_minor_planet(mplanet_int_designation):
    return get_mpc_minor_planets().iloc[mplanet_int_designation-1]


def get_mpc_minor_planet_position(mpc_minor_planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))
    c = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
    return comet_ra_ang, comet_dec_ang
