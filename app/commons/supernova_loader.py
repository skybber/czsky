import requests
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
import numpy as np

from skyfield.api import position_from_radec, load_constellation_map

from flask import (
    current_app,
)

from app import db
from app.models import (
    Constellation,
    Supernova,
)
from imports.import_utils import progress


def _to_float(s):
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(s):
    try:
        return datetime.strptime(s, '%Y/%m/%d').date()
    except ValueError:
        return None


def update_supernovae_from_rochesterastronomy():
    r = requests.get('https://www.rochesterastronomy.org/snimages/snactive.html')

    soup = BeautifulSoup(r.content, 'html.parser')

    tbl = soup.findAll('table')[1].find_all('tr')

    supernovae = []

    constellation_at = load_constellation_map()

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    for row in tbl:
        cells = row.find_all('td')
        if len(cells) > 0:
            designation = cells[0].get_text().strip()
            host_galaxy = cells[1].get_text().strip()
            ra = cells[2].get_text().strip()
            dec = cells[3].get_text().strip()
            ra = float(ra[0:2])*np.pi/12.0 + float(ra[3:5])*np.pi/(12.0*60.0) + float(ra[6:])*np.pi/(12*60.0*60)
            dec = float(dec[0]+'1')*(float(dec[1:3])*np.pi/180.0 + float(dec[4:6])*np.pi/(180.0*60) + float(dec[7:])*np.pi/(180.0*60*60))
            offset = cells[4].get_text().strip()
            latest_mag = _to_float(cells[5].get_text().strip().strip('*'))
            latest_observed = _to_date(cells[6].get_text().strip())
            sn_type = cells[7].get_text().strip()
            z = _to_float(cells[8].get_text().strip())
            max_mag = _to_float(cells[9].get_text().strip())
            max_mag_date = _to_date(cells[10].get_text().strip())
            first_observed = _to_date(cells[11].get_text().strip())
            discoverer = cells[12].get_text().strip()
            aka = cells[13].get_text().strip()

            supernova = Supernova.query.filter(Supernova.designation == designation).first()

            if not supernova:
                supernova = Supernova()

            supernova.designation = designation
            supernova.host_galaxy = host_galaxy
            supernova.ra = ra
            supernova.dec = dec
            supernova.offset = offset
            supernova.latest_mag = latest_mag
            supernova.latest_observed = latest_observed
            supernova.sn_type = sn_type
            supernova.z = z
            supernova.max_mag = max_mag
            supernova.max_mag_date = max_mag_date
            supernova.first_observed = first_observed
            supernova.discoverer = discoverer
            supernova.aka = aka

            const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))

            supernova.constellation_id = constell_dict[const_code.upper()] if const_code else None

            supernovae.append(supernova)

    for supernova in supernovae:
        db.session.add(supernova)

    try:
        db.session.commit()
    except IntegrityError as err:
        current_app.logger.error('\nIntegrity error {}'.format(err))
        db.session.rollback()
