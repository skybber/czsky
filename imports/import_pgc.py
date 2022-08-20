import numpy as np

from math import log
from app import db

from app.models.deepskyobject import DeepskyObject, Catalogue, IMPORT_SOURCE_HNSKY
from app.models.constellation import Constellation

from .import_utils import progress
from app.commons.dso_utils import get_catalog_from_dsoname
from skyfield.api import position_from_radec, load_constellation_map


def _append_found(name, found_dsos, existing_dsos):
    if name:
        found = existing_dsos.get(name)
        if found:
            found_dsos.append(found)


def _parse_pgc_line(line, existing_dsos):

    if len(line[6:37].strip()) == 0:
        return None

    pgc_num = int(line[0:5])

    ra = float(line[6:8])*np.pi/12.0 + float(line[8:10])*np.pi/(12.0*60.0) + float(line[10:14])*np.pi/(12*60.0*60)
    dec = float(line[14]+'1')*(float(line[15:17])*np.pi/180.0 + float(line[17:19])*np.pi/(180.0*60) + float(line[19:21])*np.pi/(180.0*60*60))

    try:
        maj_axis = round(float(line[43:49]) * 60)
    except ValueError:
        maj_axis = None

    try:
        min_axis = round(float(line[51:56]) * 60)
    except ValueError:
        min_axis = None

    try:
        mag = float(line[59:63])
    except ValueError:
        mag = None

    try:
        pa = int(line[73:76])
    except ValueError:
        mag = None

    name1 = line[77:93].strip().replace(' ', '')
    name2 = line[93:109].strip().replace(' ', '')
    name3 = line[109:125].strip().replace(' ', '')
    name4 = line[125:141].strip().replace(' ', '')

    found_dsos = []

    _append_found('PGC{}'.format(pgc_num), found_dsos, existing_dsos)
    _append_found(name1, found_dsos, existing_dsos)
    _append_found(name2, found_dsos, existing_dsos)
    _append_found(name3, found_dsos, existing_dsos)
    _append_found(name4, found_dsos, existing_dsos)

    if len(found_dsos) > 1:
        master_dso = None
        for d in found_dsos:
            if master_dso is None:
                if d.master_id is None:
                    master_dso = d
                else:
                    master_dso = d.masterObject
            else:
                if d != master_dso and (d.master_id is None or d.master_id != master_dso.id):
                    print('Invalid master PGC{} {} {}'.format(pgc_num, master_dso.name, d.name))


def import_pgc(filename):
    from sqlalchemy.exc import IntegrityError

    dsos = []
    sf = open(filename, 'r')
    lines = sf.readlines()
    sf.close()

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    for line in lines:
        dso = _parse_pgc_line(line, existing_dsos)
        if dso:
            dsos.append(dso)

    try:
        line_cnt = 1
        for dso in dsos:
            progress(line_cnt, len(dsos), 'Importing UGC catalogue')
            line_cnt += 1
            db.session.add(dso)
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
