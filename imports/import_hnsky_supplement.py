import numpy as np

from math import log
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.session import make_transient

from app import db

from app.models.deepskyobject import DeepskyObject, Catalogue, UserDsoDescription, UserDsoApertureDescription, \
    IMPORT_SOURCE_HNSKY, IMPORT_SOURCE_HNSKY_SUPPLEMENT
from app.models.constellation import Constellation

from .import_utils import progress
from app.commons.dso_utils import get_catalog_from_dsoname
from skyfield.api import position_from_radec, load_constellation_map

# for types look at http://simbad.u-strasbg.fr/simbad/sim-display?data=otypes
dso_type_map = {
    'GX': 'GX',
    'BN': 'BN',
    'DN': 'DN',
    'PN': 'PN',
    'OC': 'OC',
    'GC': 'GC',
    'STARS': 'STARS',
    'QUASR': 'QSO',
    'GALCL': 'GALCL',
    '2STAR': 'STARS',
    'ASTER': 'AST',
    'CL+NB': 'OC',
    'NB': 'BN',
    'PartOf': 'PartOf',
    'DN&HII': 'DN',
    'pA*':'pA*',    # Post-AGB Star (proto-PN)
    'C*':'C*',    # Carbon Star
    'CV*': 'CV*', # Cataclysmic Variable Star
    'RNe': 'RNe', # Reflection Nebula
    'NL*': 'NL*',  # Nova-like Star
    'HII': 'HII'
}

cat_priorities = {
    'M' : 1,
    'NGC' : 2,
    'IC' : 3,
    'Sh2' : 4,
    # PN catalogs
    'Abell' : 5,
    'Mi' : 6,
    'K' : 7,
    'Hen' :7,
    'Sa' : 7,
    'Vy' : 7,
    'PK' :  10000,
    'PNG' : 10001,
    # GX catalogs
    'UGC' : 5,
    'PGC' : 6,
}

def _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, save_master_dsos, hnsky_supplement_file):
    for dso in dso_list:
        if save_master_dsos:
            if dso.name in master_dso_map:
                continue
        elif dso.name not in master_dso_map:
            continue
        else:
            dso.master_id = master_dso_map[dso.name].id
        progress(line_cnt, dso_count, 'Importing Hnsky suplement {}'.format(hnsky_supplement_file))
        line_cnt += 1
        db.session.add(dso)
        db.session.flush()
    return line_cnt

def import_hnsky_supplement(hnsky_supplement_file, allowed_cat_prefixes=None):
    constellation_at = load_constellation_map()

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    suppl_file = open(hnsky_supplement_file, 'r', encoding='ISO-8859-1')
    lines = suppl_file.readlines()[2:]
    suppl_file.close()

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    dso_set = set()
    master_dso_map = {}

    pref_cats = [None] * 1000
    cat_codes = {}
    catalogs = Catalogue.query.filter(Catalogue.id < 1000).order_by(Catalogue.id)
    for cat in catalogs:
        pref_cats[cat.id - 1] = []
        cat_codes[cat.id - 1] = cat.code

    dso_count = 0
    other_dsos = []

    try:
        for line in lines:
            if len(line.strip()) == 0 or line.startswith(';'):
                continue
            items = line.split(',')

            ra = np.pi * float(items[0]) / 12.0
            if items[1].strip():
                ra += np.pi * float(items[1]) / (12.0 * 60.0)
            if items[2].strip():
                ra += np.pi * float(items[2]) / (12.0 * 60.0 * 60)
            dec = np.pi * float(items[3]) / 180.0
            mul_dec = 1 if dec >= 0 else -1
            if items[4].strip():
                dec += mul_dec * np.pi * float(items[4]) / (180.0 * 60)
            if items[5].strip():
                dec += mul_dec * np.pi * float(items[5]) / (180.0 * 60 * 60)

            const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))
            constellation_id = constell_dict[const_code.upper()] if const_code else None

            str_mag = items[6].strip()

            if str_mag:
                mag = float(str_mag) / 10.0
            else:
                mag = 100

            brightness = None
            if len(items) > 5:
                str_brightness = items[9].strip()
                try:
                    brightness = float(str_brightness) / 10.0 if str_brightness else 100.0
                except (ValueError, TypeError):
                    pass

            obj_types = items[8].split('/')

            obj_type = obj_types[0].strip()
            indx = obj_types[0].find('[')
            if indx > 0:
                obj_type = obj_type[:indx]
            indx = obj_types[0].find(';')
            if indx > 0:
                obj_type = obj_type[:indx]

            # remove uncertainty flag
            if obj_type.endswith('?') and len(obj_type) > 1:
                obj_type = obj_type[:-1]

            obj_type = dso_type_map.get(obj_type, None)

            if obj_type is None:
                print('No type {}'.format(obj_types[0].strip()))
                print(line)
                continue

            rlong = None
            str_length = items[10].strip() if len(items) > 10 else None

            if str_length:
                try:
                    rlong = float(str_length) * 6
                except (ValueError, TypeError):
                    pass

            rshort = None
            str_width = items[11].strip() if len(items) > 11 else None
            if str_width:
                try:
                    rshort = float(str_width) * 6
                except (ValueError, TypeError):
                    pass

            position_angle = None
            str_pos_angle = items[12].strip() if len(items) > 12 else None

            if str_pos_angle:
                try:
                    position_angle = float(str_pos_angle)
                except (ValueError, TypeError):
                    pass

            names = items[7].split('/')

            master_dso = None
            child_dsos = []
            master_cat_prio = None

            for name1 in names:
                if allowed_cat_prefixes:
                    allowed = False
                    for prefix in allowed_cat_prefixes:
                        if name1.startswith(prefix):
                            allowed = True
                            break
                    if not allowed:
                        continue
                for name in name1.split(';'):
                    name = name.strip()

                    if name in dso_set:
                        continue

                    dso_set.add(name)

                    cat = get_catalog_from_dsoname(name)

                    if cat:
                        dso = existing_dsos.get(name, None)

                        if dso is None:
                            dso = DeepskyObject()

                        dso.name = name
                        dso.type = obj_type
                        dso.subtype = None
                        dso.ra = ra
                        dso.dec = dec
                        dso.constellation_id = constellation_id
                        dso.catalogue_id = cat.id
                        dso.major_axis = rlong
                        dso.minor_axis = rshort
                        dso.position_angle = position_angle
                        dso.mag = mag
                        dso.surface_bright = brightness
                        dso.common_name = None
                        dso.import_source = IMPORT_SOURCE_HNSKY_SUPPLEMENT

                        cat_prio = cat_priorities.get(cat.code, 1000)

                        if (master_cat_prio is not None) and cat_prio < master_cat_prio:
                            child_dsos.append(master_dso)
                            master_dso = dso
                            master_cat_prio = cat_prio
                        elif master_dso:
                            child_dsos.append(dso)
                        else:
                            master_dso = dso
                            master_cat_prio = cat_prio

                        if cat.id < 1000:
                            pref_cats[cat.id - 1].append(dso)
                        else:
                            other_dsos.append(dso)
                        dso_count += 1

                    else:
                        print('Not found {}'.format(name))

            for child_dso in child_dsos:
                master_dso_map[child_dso.name] = master_dso
        for i in range(1000):
            dso_list = pref_cats[i]
            if not dso_list or i not in cat_codes:
                continue
            ccl = len(cat_codes[i])
            if cat_codes[i] in {'Sh2'}:  # skip '-' character in case of Sh2 object ID
                ccl += 1
            pos = int(log(len(dso_list), 10)) + 1
            # add 0 before dso ID (in catalog)
            dso_list.sort(key=lambda x: (('0' * (pos - (len(x.name) - ccl))) + x.name[ccl:]) if len(
                x.name) - ccl < pos else x.name[ccl:])

        line_cnt = 1

        # Import master DSO from preferred catalogs
        for i in range(1000):
            dso_list = pref_cats[i]
            if dso_list and i in cat_codes:
                line_cnt = _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, True, hnsky_supplement_file)

        # Import child DSO from preferred catalogs
        line_cnt = _save_dso_list(dso_count, line_cnt, other_dsos, master_dso_map, True, hnsky_supplement_file)

        for i in range(1000):
            dso_list = pref_cats[i]
            if dso_list and i in cat_codes:
                line_cnt = _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, False, hnsky_supplement_file)

        line_cnt = _save_dso_list(dso_count, line_cnt, other_dsos, master_dso_map, False, hnsky_supplement_file)

        db.session.commit()

    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('')  # finish on new line

