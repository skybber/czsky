import numpy as np

from math import log
from app import db
from sqlalchemy.exc import IntegrityError

from app.models.deepskyobject import DeepskyObject, Catalogue, IMPORT_SOURCE_PGC
from app.models.constellation import Constellation

from .import_utils import progress
from app.commons.dso_utils import get_catalog_from_dsoname
from skyfield.api import position_from_radec, load_constellation_map
from astroquery.simbad import Simbad


def _append_found(name, existing_dsos, found_dsos):
    if name:
        found_dsos.append([name, existing_dsos.get(name)])


def _create_dso(name, master_id, cat_id, ra, dec, constellation_id, rlong, rshort, position_angle, mag):
    dso = DeepskyObject()
    dso.name = name
    dso.type = 'GX'
    dso.subtype = ''
    dso.master_id = master_id
    dso.ra = ra
    dso.dec = dec
    dso.constellation_id = constellation_id
    dso.catalogue_id = cat_id
    dso.major_axis = rlong
    dso.minor_axis = rshort
    dso.position_angle = position_angle
    dso.mag = mag
    dso.surface_bright = None
    dso.common_name = None
    dso.import_source = IMPORT_SOURCE_PGC
    return dso


def import_pgc(filename):
    constellation_at = load_constellation_map()

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    master_ugc_dsos = []
    dsos = []

    sf = open(filename, 'r')
    lines = sf.readlines()
    sf.close()

    existing_dsos = {}
    existing_dso_ids = {}

    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso
        existing_dso_ids[dso.id] = dso.id

    line_cnt = 1
    total_lines = len(lines)

    for line in lines:
        progress(line_cnt, total_lines, 'Reading PGC/UGC catalogue')

        line_cnt += 1

        if len(line[6:37].strip()) == 0:
            continue

        pgc_num = int(line[0:5])

        found_dsos = []
        pgc_name = 'PGC{}'.format(pgc_num)
        _append_found(pgc_name, existing_dsos, found_dsos)

        _append_found(line[77:93].strip().replace(' ', ''), existing_dsos, found_dsos)
        _append_found(line[93:109].strip().replace(' ', ''), existing_dsos, found_dsos)
        _append_found(line[109:125].strip().replace(' ', ''), existing_dsos, found_dsos)
        _append_found(line[125:141].strip().replace(' ', ''), existing_dsos, found_dsos)

        ugc_name, ugc_dso = None, None
        for dso_name, dso in found_dsos:
            if dso_name.startswith('UGC') and not dso_name.startswith('UGCA') and dso_name != 'UGC':
                ugc_name, ugc_dso = dso_name, dso
                break

        pgc_dso = found_dsos[0][1]
        if pgc_dso is not None and ugc_dso is not None:
            continue

        ra = float(line[6:8])*np.pi/12.0 + float(line[8:10])*np.pi/(12.0*60.0) + float(line[10:14])*np.pi/(12*60.0*60)
        dec = float(line[14]+'1')*(float(line[15:17])*np.pi/180.0 + float(line[17:19])*np.pi/(180.0*60) + float(line[19:21])*np.pi/(180.0*60*60))

        try:
            rlong = round(float(line[43:49]) * 60)
        except ValueError:
            rlong = None

        try:
            rshort = round(float(line[51:56]) * 60)
        except ValueError:
            rshort = None

        try:
            mag = float(line[59:63])
        except ValueError:
            mag = 100.0

        try:
            position_angle = int(line[73:76])
        except ValueError:
            position_angle = None

        if pgc_dso is None:
            master_id = None
            for alt_dso_name, alt_dso in found_dsos:
                if alt_dso:
                    if alt_dso.master_id is not None and alt_dso.master_id in existing_dso_ids:
                        master_id = alt_dso.master_id
                    break

            const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))
            constellation_id = constell_dict[const_code.upper()] if const_code else None
            cat_pgc = get_catalog_from_dsoname(pgc_name)

            pgc_dso = _create_dso(pgc_name, master_id, cat_pgc.id, ra, dec, constellation_id, rlong, rshort, position_angle, mag)
            dsos.append(pgc_dso)

            if ugc_name is not None and ugc_dso is None:
                cat_ugc = get_catalog_from_dsoname(ugc_name)
                if master_id is None:
                    master_ugc_dsos.append([_create_dso(ugc_name, None, cat_ugc.id, ra, dec, constellation_id, rlong, rshort, position_angle, mag), pgc_dso])
                else:
                    dsos.append(_create_dso(ugc_name, master_id, cat_ugc.id, ra, dec, constellation_id, rlong, rshort, position_angle, mag))

        elif ugc_name is not None and ugc_dso is None:
            const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))
            constellation_id = constell_dict[const_code.upper()] if const_code else None
            cat_ugc = get_catalog_from_dsoname(ugc_name)
            if pgc_dso.master_id is not None and pgc_dso.master_id in existing_dso_ids:
                dsos.append(_create_dso(ugc_name, pgc_dso.master_id, cat_ugc.id, ra, dec, constellation_id, rlong, rshort, position_angle, mag))
            else:
                master_ugc_dsos.append([_create_dso(ugc_name, None, cat_ugc.id, ra, dec, constellation_id, rlong, rshort, position_angle, mag), pgc_dso])
                dsos.append(pgc_dso)

    try:
        cnt = 1
        total = len(master_ugc_dsos) + len(dsos)
        for ugc_dso, pgc_dso in master_ugc_dsos:
            progress(cnt, total, 'Importing PGC/UGC catalogue')
            db.session.add(ugc_dso)
            db.session.flush()
            pgc_dso.master_id = ugc_dso.id
            cnt += 1

        for dso in dsos:
            progress(cnt, total, 'Importing PGC/UGC catalogue')
            db.session.add(dso)
            cnt += 1

        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()


def create_pgc_update_file_from_simbad(pgc_file, output_file):
    with open(pgc_file, 'r') as sf:
        inp_lines = sf.readlines()

    try:
        with open(output_file, 'r') as sf:
            gen_lines = sf.readlines()
    except:
        gen_lines = []

    if len(gen_lines) > 0:
        last_pgc = int(gen_lines[-1].split()[0][3:])
    else:
        last_pgc = 0

    simbad = Simbad()
    simbad.add_votable_fields('dim_majaxis', 'dim_minaxis', 'dim_angle')

    line_cnt = 1
    total_lines = len(inp_lines)

    with open(output_file, 'a') as fout:
        for line in inp_lines:
            line_cnt += 1

            if len(line[6:37].strip()) == 0:
                continue

            pgc_num = int(line[0:5])

            if pgc_num <= last_pgc:
                continue

            pgc_name = 'PGC{}'.format(pgc_num)
            try:
                progress(line_cnt, total_lines, 'Reading {}'.format(pgc_name))
                dso = simbad.query_object(pgc_name)
                s_ra = dso[0]['RA']
                s_dec = dso[0]['DEC']

                try:
                    ra = float(s_ra[0:2]) * np.pi / 12.0 + float(s_ra[3:5]) * np.pi / (12.0 * 60.0) + float(s_ra[6:10]) * np.pi / (12 * 60.0 * 60)
                    dec = float(s_dec[0] + '1') * (float(s_dec[1:3]) * np.pi / 180.0 + float(s_dec[4:6]) * np.pi / (180.0 * 60) + float(s_dec[7:9]) * np.pi / (180.0 * 60 * 60))
                except (IndexError, ValueError) as er:
                    ra = '-'
                    dec = '-'

                fout.write('{} {} {} {} {} {}\n'.format(pgc_name, ra, dec, dso[0]['GALDIM_MAJAXIS'], dso[0]['GALDIM_MINAXIS'], dso[0]['GALDIM_ANGLE']))
                if line_cnt % 50 == 0:
                    fout.flush()
            except TypeError:
                pass


def update_pgc_imported_dsos_from_updatefile(pgc_update_file):
    with open(pgc_update_file, 'r') as sf:
        lines = sf.readlines()

    dsos = DeepskyObject.query.filter_by(import_source=IMPORT_SOURCE_PGC, major_axis=None).all()

    dso_map = {}

    for dso in dsos:
        dso_map[dso.name] = dso

    line_cnt = 1
    total_lines = len(lines)

    max_ang_diff = np.pi / (60.0 * 180.0)

    try:
        for line in lines:
            progress(line_cnt, total_lines, 'Updating PGC data...')
            line_cnt += 1
            dso_name, s_ra, s_dec, major, minor, angle = line.split()
            dso = dso_map.get(dso_name)
            if not dso:
                continue
            try:
                ra = float(s_ra) if s_ra != '-' else None
                dec = float(s_dec) if s_dec != '-' else None

                if ra is not None and dec is not None:
                    ra_diff = abs(ra - dso.ra)
                    dec_diff = abs(dec - dso.dec)
                    if ra_diff > max_ang_diff or dec_diff > max_ang_diff:
                        print('Max angular diff exceeded for {} ra_diff={} dec_diff={}'.format(dso_name, ra_diff, dec_diff))
                        continue

                major = round(float(major) * 60.0)
                if minor == '-':
                    minor = major
                else:
                    minor = round(float(minor) * 60.0)
                axis_ratio = 1
                if major < minor:
                    major, minor = minor, major
                if major > 0:
                    axis_ratio = minor / major
                if angle != '-':
                    position_angle = np.pi * float(angle) / 180
                else:
                    position_angle = None
                dso.ra = ra
                dso.dec = dec
                dso.major_axis = major
                dso.minor_axis = minor
                dso.axis_ratio = axis_ratio
                dso.position_angle = position_angle
                db.session.add(dso)
                if dso.master_dso is not None and dso.master_dso.import_source == IMPORT_SOURCE_PGC \
                        and dso.master_dso.name.startswith('UGC') and dso.master_dso.major_axis is None:
                    dso.master_dso.major_axis = major
                    dso.master_dso.minor_axis = minor
                    dso.master_dso.axis_ratio = axis_ratio
                    db.session.add(dso.master_dso)
            except ValueError:
                pass
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
