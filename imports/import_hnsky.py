import numpy as np

from math import log
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.session import make_transient

from app import db

from app.models.deepskyobject import DeepskyObject, Catalogue, UserDsoDescription, UserDsoApertureDescription, IMPORT_SOURCE_HNSKY
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


def _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, save_master_dsos):
    for dso in dso_list:
        if save_master_dsos:
            if dso.name in master_dso_map:
                continue
        elif dso.name not in master_dso_map:
            continue
        else:
            dso.master_id = master_dso_map[dso.name].id
        progress(line_cnt, dso_count, 'Importing Hnsky DSOs')
        line_cnt += 1
        db.session.add(dso)
        db.session.flush()
    return line_cnt


def import_hnsky(hnsky_dso_file):

    constellation_at = load_constellation_map()

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    hnd_file = open(hnsky_dso_file, 'r', encoding='ISO-8859-1')
    lines = hnd_file.readlines()[2:]
    hnd_file.close()

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    dso_set = set()
    master_dso_map = {}
    main_dso_list = []

    pref_cats = [None] * 1000
    cat_codes = {}
    catalogs = Catalogue.query.filter(Catalogue.id<1000).order_by(Catalogue.id)
    for cat in catalogs:
        pref_cats[cat.id-1] = []
        cat_codes[cat.id-1] = cat.code

    dso_count = 0
    other_dsos = []

    try:
        for line in lines:
            if len(line) == 0:
                continue
            items = line.split(',')

            ra = 2.0 * np.pi * float(items[0])/864000.0
            dec = np.pi * float(items[1])/(324000.0 * 2.0)

            const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))
            constellation_id = constell_dict[const_code.upper()] if const_code else None

            str_mag = items[2].strip()
            mag = float(str_mag)/10.0 if str_mag else 100.0

            brightness = None
            if len(items) > 5:
                str_brightness = items[5].strip()
                try:
                    brightness = float(str_brightness)/10.0 if str_brightness else 100.0
                except (ValueError, TypeError):
                    pass
                
            obj_types = items[4].split('/')

            obj_type = obj_types[0].strip()
            indx = obj_types[0].find('[')
            if indx > 0:
                obj_type = obj_type[:indx]
            indx = obj_types[0].find(';')
            if indx > 0:
                obj_type = obj_type[:indx]

            indx1 = items[4].find('[')
            indx2 = items[4].find(']')
            obj_subtype = items[4][indx1+1:indx2] if indx1<indx2 else None

            # remove uncertainty flag
            if obj_type.endswith('?') and len(obj_type) > 1:
                obj_type = obj_type[:-1]
                
            obj_type = dso_type_map.get(obj_type, None)

            if obj_type is None:
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
            child_dsos = []
            master_cat_prio = None

            for name1 in names:
                for name in name1.split(';'):
                    name = name.strip()
                    
                    if name.startswith('PN_'):
                        name = name[3:]
                        
                    if name.startswith('A66_'):
                        name = 'Abell' + name[4:]

                    if name.startswith('PK_'):
                        name = 'PK' + _denormalize_pk_name(name[3:])

                    if name.startswith('Arp_'):
                        name = 'Arp' + name[4:]

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
                        dso.constellation_id = constellation_id
                        dso.catalogue_id = cat.id
                        dso.major_axis = rlong
                        dso.minor_axis = rshort
                        dso.position_angle = position_angle
                        dso.mag = mag
                        dso.surface_bright = brightness
                        dso.common_name = None
                        dso.import_source = IMPORT_SOURCE_HNSKY

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
                            pref_cats[cat.id-1].append(dso)
                        else:
                            other_dsos.append(dso)
                        dso_count += 1
                            
                    else:
                        print('Not found {}'.format(name))

            for child_dso in child_dsos:
                master_dso_map[child_dso.name] = master_dso

            if master_dso:
                for name1 in names:
                    for name in name1.split(';'):
                        name = name.strip()
                        if name.startswith('NGC') or name.startswith('IC') or name.startswith('UGC'):
                            if name.endswith('A'):
                                main_dso_list.append((name[:-1], master_dso))
                            elif name.endswith('-1') or name.endswith('_1'):
                                main_dso_list.append((name[:-2], master_dso))


        # Sort dso in catalog list according object number in catalog
        for i in range(1000):
            dso_list = pref_cats[i]
            if not dso_list or i not in cat_codes:
                continue
            ccl = len(cat_codes[i])
            if cat_codes[i] in { 'Sh2' }: # skip '-' character in case of Sh2 object ID
                ccl += 1
            pos = int(log(len(dso_list), 10)) + 1
            # add 0 before dso ID (in catalog)
            dso_list.sort(key=lambda x: (('0' * (pos - (len(x.name) - ccl))) + x.name[ccl:]) if len(x.name) - ccl <  pos else x.name[ccl:])
        
        line_cnt = 1

        # Import master DSO from preferred catalogs 
        for i in range(1000):
            dso_list = pref_cats[i]
            if dso_list and i in cat_codes:
                line_cnt = _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, True)

        # Import child DSO from preferred catalogs
        line_cnt = _save_dso_list(dso_count, line_cnt, other_dsos, master_dso_map, True) 
            
        for i in range(1000):
            dso_list = pref_cats[i]
            if dso_list and i in cat_codes:
                line_cnt = _save_dso_list(dso_count, line_cnt, dso_list, master_dso_map, False)

        line_cnt = _save_dso_list(dso_count, line_cnt, other_dsos, master_dso_map, False)

        for name, master_dso in main_dso_list:
            if name in dso_set:
                continue

            print('Creating fake {}'.format(name))
            dso = existing_dsos.get(name, None)

            if dso is None:
                dso = DeepskyObject()

            dso.name = name
            dso.type = master_dso.type
            dso.subtype = master_dso.subtype
            dso.ra = master_dso.ra
            dso.dec = master_dso.dec
            dso.constellation_id = master_dso.constellation_id
            dso.catalogue_id = master_dso.catalogue_id
            dso.major_axis = master_dso.major_axis
            dso.minor_axis = master_dso.minor_axis
            dso.position_angle = master_dso.position_angle
            dso.mag = master_dso.mag
            dso.surface_bright = master_dso.surface_bright
            dso.common_name = master_dso.common_name
            dso.import_source = IMPORT_SOURCE_HNSKY
            dso.master_id = master_dso.id
            db.session.add(dso)

        db.session.commit()

    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line


def _denormalize_pk_name(name):
    denorm = ''
    compress = True
    outp = False
    for i in range(0, len(name)):
        c = name[i]
        if compress and c == '0':
            continue 
        if not c.isdigit():
            if not outp:
                denorm += '0'
            compress = True
            outp = False
        else:
            outp = True
            compress = False
        denorm += c
    return denorm


def fix_masters_after_hnsky_import():
    cat_prefixes = ['NGC', 'IC' ]
    try:
        print('Fixing masters after hnsky import...')
        for cat_pref in cat_prefixes:
            dso_map = {}
            all_dso = DeepskyObject.query.filter(DeepskyObject.name.like(cat_pref + '%\\__', escape='\\')).all()
            for dso in all_dso:
                master_name = dso.name[:dso.name.index('_')]
                if master_name not in dso_map:
                    dso_map[master_name] = []
                dso_map[master_name].append(dso)

            for dso_name in dso_map:
                master = DeepskyObject.query.filter_by(name=dso_name).first()
                max_dso = None
                for child in dso_map[dso_name]:
                    if max_dso is None or ((max_dso.major_axis is None and child.major_axis is not None) or
                                           (max_dso.major_axis is not None and child.major_axis is not None and max_dso.major_axis < child.major_axis)):
                        max_dso = child
                    child.master_id = None

                max_dso.master_id = master.id

                for child in dso_map[dso_name]:
                    db.session.add(child)

                master.master_id = None
                master.type = max_dso.type
                master.subtype = max_dso.subtype
                master.ra = max_dso.ra
                master.dec = max_dso.dec
                master.constellation_id = max_dso.constellation_id
                master.catalogue_id = max_dso.catalogue_id
                master.major_axis = max_dso.major_axis
                master.minor_axis = max_dso.minor_axis
                master.axis_ratio = max_dso.axis_ratio
                master.position_angle = max_dso.position_angle
                master.mag = max_dso.mag
                master.surface_bright = max_dso.surface_bright
                master.c_star_b_mag = max_dso.c_star_b_mag
                master.c_star_v_mag = max_dso.c_star_v_mag
                master.distance = max_dso.distance
                master.common_name = max_dso.common_name
                master.descr = max_dso.descr
                master.import_source = max_dso.import_source
                db.session.add(master)

        db.session.commit()

    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line
