import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name

from .import_utils import progress

def fix_cstar_from_open_ngc(open_ngc_data_file):
    """
    Get missing cstar data from openngc
    """
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    row_count = sum(1 for line in open(open_ngc_data_file)) - 1

    dso = DeepskyObject.query.all()

    with open(open_ngc_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            row_id = 0
            for row in reader:
                progress(row_id, row_count, 'Fixing Hnsky from OpenNGC')
                row_id += 1
                constellation = row['Const']

                if constellation in ['Se1', 'Se2']:
                    constellation = 'Ser'

                dso_name = denormalize_dso_name(row['Name']).replace(' ', '')

                dso = existing_dsos.get(dso_name, None)

                if dso is None:
                    continue

                dso.constellation_id = constell_dict[constellation.upper()] if constellation else None
                dso.c_star_b_mag = float(row['Cstar B-Mag']) if row['Cstar B-Mag'] else None
                dso.c_star_v_mag = float(row['Cstar V-Mag']) if row['Cstar V-Mag'] else None
                dso.common_name = row['Common names']
                dso.descr = row['NED notes']

                db.session.add(dso)

                if row['M'] or dso.name=='NGC5866':
                    mes_id = row['M']

                    if not mes_id:
                        mes_id = '102'

                    mes_dso = existing_dsos.get('M' + mes_id.lstrip('0'), None)
                    if mes_dso is None:
                        continue

                    mes_dso.constellation_id = dso.constellation_id
                    mes_dso.c_star_b_mag = dso.c_star_b_mag
                    mes_dso.c_star_v_mag = dso.c_star_v_mag
                    mes_dso.common_name = dso.common_name
                    mes_dso.descr = dso.descr

                    db.session.add(mes_dso)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('')


def fix_hnsky_constell_from_sac(sac_data_file):
    """
    Get missing constellation from SAC catalog
    """
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    row_count = sum(1 for line in open(sac_data_file)) - 1

    with open(sac_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        row_id = 0
        try:
            for row in reader:
                progress(row_id, row_count, 'Fixing Hnsky from SAC catalogue')
                row_id += 1

                dso_name = row['OBJECT'].strip().replace(' ', '')
                dso_name = normalize_dso_name(dso_name)

                dso = existing_dsos.get(dso_name, None)

                if not dso:
                    continue

                constellation_id = constell_dict.get(row['CON'].upper(), None)

                if not dso.constellation_id:
                    dso.constellation_id = constellation_id
                    db.session.add(dso)

                other_name = row['OBJECT'].strip().replace(' ', '')
                if not other_name:
                    continue

                other_name = normalize_dso_name(other_name)
                other_dso = existing_dsos.get(other_name, None)

                if not other_dso:
                    continue

                if not other_dso.constellation_id:
                    other_dso.constellation_id = constellation_id
                    db.session.add(other_dso)

            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line

