import requests
import re
import datetime
import calendar
from bs4 import BeautifulSoup
from flask import current_app

from sqlalchemy.exc import IntegrityError

from app import db

from app import scheduler

from app.models import (
    Comet,
    CometObservation,
)


def update_comets_observations():
    r = requests.get('https://cobs.si/cobs/recent/')

    soup = BeautifulSoup(r.content, 'html.parser')

    all_comets_text = soup.select('p.text-info')

    month_2_index = {month.lower(): index for index, month in enumerate(calendar.month_abbr) if month}

    new_observations = []

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
                                    notes = obs_parts[1][:obs_parts[1].index(')')]

                                    coma_diameter = None
                                    if diams != '':
                                        coma_diameters = re.findall(r'\d+(?:\.\d*)?', diams)
                                        coma_diameter = float(coma_diameters[0]) if len(coma_diameters) > 0 else None
                                        if diams.endswith('"'):
                                            coma_diameter = coma_diameter * 60.0

                                    date = None
                                    try:
                                        day_tm = float(day_tms)
                                        day = int(float(day_tm))
                                        hour_tm = (day_tm % 1) * 24
                                        hour = int(hour_tm)
                                        minute_tm = (hour_tm % 1) * 60
                                        minute = int(minute_tm)
                                        second_tm = (minute_tm % 1) * 60
                                        second = int(second_tm)
                                        date = datetime.datetime(year=int(year), month=month_2_index[month.lower()], day=day, hour=hour, minute=minute, second=second)
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
                                            current_app.logger.error('Can\'t find comet={}'.format(comet_name))

    current_app.logger.info('Comets\' observations loaded.')


job = scheduler.add_job(update_comets_observations, 'interval', hours=12, replace_existing=True)
