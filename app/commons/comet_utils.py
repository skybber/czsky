from io import BytesIO

import requests
import re
import datetime
import calendar
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
import numpy as np

from datetime import datetime, timedelta
import datetime as dt_module

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.api import position_from_radec, load_constellation_map


from flask import (
    current_app,
)

from app import db
from app.models import (
    Comet,
    CometObservation,
    Constellation,
)
from imports.import_utils import progress

utc = dt_module.timezone.utc

# comets intended to be periodically updated, so it is not part of import package

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
            if o.mag is not None:
                mag = (mag+o.mag) if mag is not None else mag
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

        after = datetime.today() - timedelta(days=31)
        for comet in Comet.query.filter_by().all():
            mag, coma_diameter = comet.eval_mag, None
            real_mag = False
            observs = CometObservation.query.filter_by(comet_id=comet.id) \
                                            .filter(CometObservation.date >= after) \
                                            .order_by(CometObservation.date.desc()) \
                                            .all()[:5]

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


def load_all_mpc_comets(reload_comets):
    with load.open(mpc.COMET_URL, reload=reload_comets) as f:
        all_mpc_comets = mpc.load_comets_dataframe_slow(f)
        all_mpc_comets = (all_mpc_comets.sort_values('reference')
                          .groupby('designation', as_index=False).last()
                          .set_index('designation', drop=False))
        all_mpc_comets['comet_id'] = np.where(all_mpc_comets['designation_packed'].isnull(), all_mpc_comets['designation'], all_mpc_comets['designation_packed'])
        all_mpc_comets['comet_id'] = all_mpc_comets['comet_id'].str.replace('/','')
        all_mpc_comets['comet_id'] = all_mpc_comets['comet_id'].str.replace(' ', '')
        return all_mpc_comets


def _save_comets(comets, show_progress, progress_title):
    try:
        line_cnt = 1
        for comet in comets:
            if show_progress:
                progress(line_cnt, len(comets), progress_title)
            line_cnt += 1
            db.session.add(comet)
        if show_progress:
            print('')
        db.session.commit()
    except IntegrityError as err:
        current_app.logger.error('\nIntegrity error {}'.format(err))
        db.session.rollback()


def import_update_comets(all_mpc_comets, show_progress=False):
    comets = []

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()

    sun, earth = eph['sun'], eph['earth']
    constellation_at = load_constellation_map()

    for index, mpc_comet in all_mpc_comets.iterrows():
        comet_id = mpc_comet['comet_id']
        
        comet = Comet.query.filter_by(comet_id=comet_id).first()
        if comet is None:
            comet = Comet()
            comet.comet_id = comet_id

            skf_comet = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)
            dist_earth = earth.at(t).observe(skf_comet).distance().au
            dist_sun = sun.at(t).observe(skf_comet).distance().au
            m = mpc_comet['magnitude_g'] + 5.0*np.log10(dist_earth) + 2.5*mpc_comet['magnitude_k']*np.log10(dist_sun)
            comet.eval_mag = m

            comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(skf_comet).radec()
            comet.cur_ra = comet_ra_ang.radians
            comet.cur_dec = comet_dec_ang.radians
            const_code = constellation_at(position_from_radec(comet_ra_ang.radians / np.pi * 12.0, comet_dec_ang.radians / np.pi * 180.0))
            comet.cur_constell_id = Constellation.get_constellation_by_iau_code(const_code).id

        comet.designation = mpc_comet['designation']
        comet.number = mpc_comet['number']
        comet.orbit_type = mpc_comet['orbit_type']
        comet.designation_packed = mpc_comet['designation_packed']
        comet.perihelion_year = mpc_comet['perihelion_year']
        comet.perihelion_month = mpc_comet['perihelion_month']
        comet.perihelion_day = mpc_comet['perihelion_day']
        comet.perihelion_distance_au = mpc_comet['perihelion_distance_au']
        comet.eccentricity = mpc_comet['eccentricity']
        comet.argument_of_perihelion_degrees = mpc_comet['argument_of_perihelion_degrees']
        comet.longitude_of_ascending_node_degrees = mpc_comet['longitude_of_ascending_node_degrees']
        comet.inclination_degrees = mpc_comet['inclination_degrees']
        comet.perturbed_epoch_year = mpc_comet['perturbed_epoch_year']
        comet.perturbed_epoch_month = mpc_comet['perturbed_epoch_month']
        comet.perturbed_epoch_day = mpc_comet['perturbed_epoch_day']
        comet.magnitude_g = mpc_comet['magnitude_g']
        comet.magnitude_k = mpc_comet['magnitude_k']
        comet.reference = mpc_comet['reference']
        comets.append(comet)
    _save_comets(comets, show_progress, 'Importing comets...')
    current_app.logger.info('Comets\' updated.')


def update_evaluated_comet_brightness(all_mpc_comets=None, show_progress=False, reload_comets=True):
    if all_mpc_comets is None:
        all_mpc_comets = load_all_mpc_comets(reload_comets)
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    t = ts.now()

    comets = []
    for index, mpc_comet in all_mpc_comets.iterrows():
        m = 22.0
        try:
            skf_comet = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)
            dist_earth = earth.at(t).observe(skf_comet).distance().au
            dist_sun = sun.at(t).observe(skf_comet).distance().au
            m = mpc_comet['magnitude_g'] + 5.0*np.log10(dist_earth) + 2.5*mpc_comet['magnitude_k']*np.log10(dist_sun)
            current_app.logger.info('Comet: {} de={} ds={} m={} g={}'.format(mpc_comet['designation'], dist_earth, dist_sun, m, mpc_comet['magnitude_k']))
            comet = Comet.query.filter_by(comet_id=mpc_comet['comet_id']).first()
            if comet:
                comet.eval_mag = m
                comets.append(comet)
        except Exception as err:
            current_app.logger.error('\nError {}'.format(err))
            pass

    _save_comets(comets, show_progress, 'Saving comets...')
    current_app.logger.info('Comets\' evaluated brightness updated.')


def update_comets_cobs_observations():
    r = requests.get('https://cobs.si/recent/')

    soup = BeautifulSoup(r.content, 'html.parser')

    all_comets_text = soup.select('p.text-info')

    month_2_index = { month.lower(): index for index, month in enumerate(calendar.month_abbr) if month }

    for comet_text in all_comets_text:
        parts = comet_text.find_all('strong', recursive=False)
        year_observs = comet_text.select('code', recursive=False)
        if parts and year_observs:
            comet_name = parts[0].select_one('a')
            if not comet_name:
                continue
            comet_name = comet_name.text
            for i in range(1, len(parts)):
                year = parts[i].text
                if (i - 1) < len(year_observs):
                    yo = year_observs[i-1]
                    if year and yo:
                        observs = ' '.join(yo.decode_contents().split()).split('<br/>')
                        month = None
                        for obs in observs:
                            obs_parts = obs.split('(', 1)
                            if len(obs_parts) == 2:
                                obs_items = obs_parts[0].split(',')
                                if len(obs_items) >= 3:
                                    date_month = obs_items[0].split()
                                    if len(date_month) == 2:
                                        month = date_month[0]
                                        day_tms = date_month[1]
                                    else:
                                        day_tms = date_month[0]
                                    mags = re.findall(r'\d+(?:\.\d*)?', obs_items[1])
                                    mag = float(mags[0]) if len(mags) > 0 else None
                                    diams = obs_items[2].strip()
                                    notes = obs_parts[1][:obs_parts[1].index(';')-1]

                                    coma_diameter = None
                                    if diams != '':
                                        coma_diameters = re.findall(r'\d+(?:\.\d*)?', diams)
                                        coma_diameter = float(coma_diameters[0]) if len(coma_diameters) > 0 else None
                                        if diams.endswith('"'):
                                            coma_diameter = coma_diameter * 60.0

                                    try:
                                        day_tm = float(day_tms)
                                        day = int(float(day_tm))
                                        hour_tm = (day_tm % 1) * 24
                                        hour = int(hour_tm)
                                        minute_tm = (hour_tm % 1) * 60
                                        minute = int(minute_tm)
                                        second_tm = (minute_tm % 1) * 60
                                        second = int(second_tm)
                                        date = datetime(year=int(year), month=month_2_index[month.lower()], day=day, hour=hour, minute=minute, second=second)
                                    except ValueError:
                                        current_app.logger.error('Can\'t create datetime comet={} year={} month={} day={}'.format(comet_name, year, month, day_tms))
                                        continue

                                    if date is not None:
                                        comet_name = comet_name.split('(')[0].strip()
                                        comet = Comet.query.filter(Comet.designation.like(comet_name.strip() + '%')).first()
                                        if comet:
                                            comet_observation = CometObservation.query.filter_by(comet_id=comet.id, date=date, mag=mag).first()
                                            if not comet_observation:
                                                comet_observation = CometObservation(
                                                    comet_id=comet.id,
                                                    date=date,
                                                    mag=mag,
                                                    coma_diameter=coma_diameter,
                                                    notes=notes
                                                )
                                                try:
                                                    db.session.add(comet_observation)
                                                    db.session.commit()
                                                except IntegrityError as err:
                                                    current_app.logger.error('\nIntegrity error {}'.format(err))
                                                    db.session.rollback()
                                        else:
                                            current_app.logger.warn('Can\'t find comet={}'.format(comet_name))

    # update brightness from COBS
    try:
        db.session.commit()
        after = datetime.today() - timedelta(days=31)
        for comet in Comet.query.filter_by().all():
            observs = CometObservation.query.filter_by(comet_id=comet.id) \
                                            .filter(CometObservation.date >= after) \
                                            .order_by(CometObservation.date.desc()) \
                                            .all()[:5]

            if len(observs) > 0:
                mag, coma_diameter = get_mag_coma_from_observations(observs)
                comet.mag = mag
                comet.real_mag = mag
                comet.real_coma_diameter = coma_diameter
                db.session.add(comet)
            else:
                comet.mag = comet.eval_mag
                comet.real_mag = None
                comet.real_coma_diameter = None
                db.session.add(comet)
    except IntegrityError as err:
        current_app.logger.error('\nIntegrity error {}'.format(err))
        db.session.rollback()

    current_app.logger.info('Comets\' cobs observations loaded.')


def update_comets_positions(all_mpc_comets=None, show_progress=False, reload_comets=True):
    if all_mpc_comets is None:
        all_mpc_comets = load_all_mpc_comets(reload_comets)

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()

    sun, earth = eph['sun'], eph['earth']
    constellation_at = load_constellation_map()

    comets = []

    for db_comet in Comet.query.all():
        c = all_mpc_comets.loc[all_mpc_comets['comet_id'] == db_comet.comet_id]
        mpc_comet = c.iloc[0] if len(c) > 0 else None
        if mpc_comet is not None:
            skf_comet = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)
            ra_ang, dec_ang, distance = earth.at(t).observe(skf_comet).radec()
            db_comet.cur_ra = ra_ang.radians
            db_comet.cur_dec = dec_ang.radians
            const_code = constellation_at(position_from_radec(ra_ang.radians / np.pi * 12.0, dec_ang.radians / np.pi * 180.0))
            db_comet.cur_constell_id = Constellation.get_constellation_by_iau_code(const_code).id if const_code else None

            comets.append(db_comet)

    _save_comets(comets, show_progress, 'Saving comets...')
    current_app.logger.info('Comets\' positions updated.')
