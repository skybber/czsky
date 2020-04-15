import numpy as np

from math import log
from app import db
from app.models.deepskyobject import DeepskyObject, Catalogue

from .import_utils import progress
from app.commons.dso_utils import get_catalog_from_dsoname

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
    'DN&HII': 'DN'
}


def _save_pref_cat_dsos(cat_codes, pref_dso_count, line_cnt, dso_list, i, master_dso_map, master_dsos):
    ccl = len(cat_codes[i])
    if cat_codes[i] in { 'Sh2' }: # skip '-' character in case of Sh2 object ID
        ccl += 1
    pos = int(log(len(dso_list), 10)) + 1
    dso_list.sort(key=lambda x: (('0' * (pos - (len(x.name) - ccl))) + x.name[ccl:]) if len(x.name) - ccl <  pos else x.name[ccl:])
    for dso in dso_list:
        if master_dsos:
            if dso.name in master_dso_map:
                continue
        elif not dso.name in master_dso_map:
            continue
        else:
            dso.master_id = master_dso_map[dso.name].id
        progress(line_cnt, pref_dso_count, 'Importing prefered catalog DSOs')
        line_cnt += 1
        db.session.add(dso)
        db.session.flush()
    return line_cnt


def import_hnsky(hnsky_dso_file):

    from sqlalchemy.exc import IntegrityError

    hnd_file = open(hnsky_dso_file, 'r', encoding='ISO-8859-1')
    lines   = hnd_file.readlines()[2:]
    hnd_file.close()

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    dso_set = set()
    master_dso_map = {}

    pref_cats = [None] * 1000
    cat_codes = {}
    catalogs = Catalogue.query.filter(Catalogue.id<1000).order_by(Catalogue.id)
    for cat in catalogs:
        pref_cats[cat.id-1] = []
        cat_codes[cat.id-1] = cat.code

    pref_dso_count = 0
    other_dsos = []

    try:
        for line in lines:
            items = line.split(',')

            ra = 2.0 * np.pi * float(items[0])/864000.0
            dec = np.pi * float(items[1])/(324000.0 * 2.0)
            str_mag = items[2].strip()
            mag = float(str_mag)/10.0 if str_mag else 100.0

            brightness = None
            if len(items) > 5:
                str_brightness = items[5].strip()
                brightness = float(str_brightness)/10.0 if str_brightness else 100.0

            obj_types = items[4].split('/')

            obj_type = obj_types[0].strip()
            indx = obj_types[0].find('[')
            if indx>0:
                obj_type = obj_type[:indx]
            indx = obj_types[0].find(';')
            if indx>0:
                obj_type = obj_type[:indx]

            indx1 = items[4].find('[')
            indx2 = items[4].find(']')
            obj_subtype = items[4][indx1+1:indx2] if indx1<indx2 else None

            obj_type = dso_type_map.get(obj_type, None)

            if obj_type == None:
                print('No type {}'.format(obj_types[0].strip()))
                print(line)
                continue

            rlong = None
            str_length = items[6].strip() if len(items) > 6 else None

            if str_length:
                try:
                    rlong = float(str_length) * 6
                except (ValueError, TypeError):
                    pass

            rshort = None
            str_width = items[7].strip() if len(items) > 7 else None
            if str_width:
                try:
                    rshort = float(str_width) * 6
                except (ValueError, TypeError):
                    pass

            position_angle = None
            str_pos_angle = items[8].strip() if len(items) > 8 else None

            if str_pos_angle:
                try:
                    position_angle = float(str_pos_angle)
                except (ValueError, TypeError):
                    pass

            names = items[3].split('/')

            master_dso = None
            prev_dso = None
            prev_dsos = []
            for name1 in names:
                for name in name1.split(';'):
                    name = name.strip()

                    if (name.startswith('NGC') or name.startswith('IC') or name.startswith('UGC')):
                        if name.endswith('A'):
                            name = name[:-1]
                        elif name.endswith('-1') or name.endswith('_1'):
                            name = name[:-2]

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
                        dso.subtype = obj_subtype
                        dso.ra = ra
                        dso.dec = dec
                        dso.constellation_id = None
                        dso.catalogue_id = cat.id
                        dso.major_axis = rlong
                        dso.minor_axis = rshort
                        dso.positon_angle = position_angle
                        dso.mag = mag
                        dso.surface_bright = brightness
                        dso.common_name = None

                        if cat.code == 'Abell' and prev_dso and \
                           (prev_dso.name.startswith('PK') or prev_dso.name.startswith('Sh2')):
                            for pdso in prev_dsos:
                                master_dso_map[pdso.name] = dso
                            master_dso = dso
                        elif master_dso:
                            master_dso_map[name] = master_dso
                        else:
                            master_dso = dso

                        prev_dso = dso
                        prev_dsos.append(dso)
                        if cat.id < 1000:
                            pref_cats[cat.id-1].append(dso)
                            pref_dso_count += 1
                        else:
                            other_dsos.append(dso)
                    else:
                        print('Not found {}'.format(name))

        line_cnt = 1
        for i in range(1000):
            dso_list = pref_cats[i]
            if not dso_list:
                continue
            if not i in cat_codes:
                continue
            line_cnt = _save_pref_cat_dsos(cat_codes, pref_dso_count, line_cnt, dso_list, i, master_dso_map, True)

        for i in range(1000):
            dso_list = pref_cats[i]
            if not dso_list:
                continue
            if not i in cat_codes:
                continue
            line_cnt = _save_pref_cat_dsos(cat_codes, pref_dso_count, line_cnt, dso_list, i, master_dso_map, False)

        line_cnt = 1
        print('')
        for dso in other_dsos:
            progress(line_cnt, len(other_dsos), 'Importing Hnsky DSOs')
            line_cnt += 1
            if dso.name in master_dso_map:
                dso.master_id = master_dso_map[dso.name].id
            db.session.add(dso)
            db.session.flush()
        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line
