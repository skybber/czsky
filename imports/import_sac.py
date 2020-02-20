import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from skyfield.units import Angle

from app.commons.dso_utils import normalize_dso_name
from .import_utils import progress

dso_type_mappings = {
    'GALXY': 'Glx',
    'OPNCL' : 'OC',
    'PLNNB' : 'PN',
    'GALCL' : 'GCl'
}

def get_size(d):
    d = d.replace(' ','')
    if d.startswith('<'):
        d = d[1:]
    if not d:
        return None
    frac = 1.0
    if d.endswith('s'):
        d = d[:-1]
        frac = 60.0
    if d.endswith('m'):
        d = d[:-1]
    if d.endswith('?'):
        d = d[:-1]
    return float(d) / frac

def import_sac(sac_data_file):
    """Import Saguaro astronomy club catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.name.upper()] = co.id

    row_count = sum(1 for line in open(sac_data_file)) - 1

    with open(sac_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        row_id = 0
        try:
            for row in reader:
                progress(row_id, row_count, 'Importing SAC catalogue')
                row_id += 1
                create_synonymas = False
                catalogue_id = None
                object_name = row['OBJECT'].strip()
                if object_name.startswith('Abell '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Abell')
                elif object_name.startswith('Cr '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Cr')
                elif object_name.startswith('Pal '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Pal')
                elif object_name.startswith('PK '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('PK')
                elif object_name.startswith('Stock '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Stock')
                elif object_name.startswith('UGC '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('UGC')
                elif object_name.startswith('Mel '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Mel')
                elif object_name.startswith('LDN '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('LDN')
                elif object_name.startswith('B') and (object_name[1]==' ' or object_name[1].isdigit()):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('B')
                elif object_name.startswith('NGC '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('NGC')
                    create_synonymas = True
                elif object_name.startswith('IC'):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('IC')

                if not catalogue_id:
                    continue

                str_mag = row['MAG'].strip()
                if str_mag.endswith('p'):
                    str_mag = str_mag[:-1]

                mag = float(str_mag) if str_mag else None

                object_name = normalize_dso_name(object_name)
                dso_type = dso_type_mappings.get(row['TYPE'], row['TYPE'])
                constellation_id = constell_dict.get(row['CON'].upper(), None)

                existing_dso = DeepskyObject.query.filter_by(name=object_name).first()

                # Fix OpenNGC missing visual mag
                if existing_dso:
                    existing_dso.mag = mag
                    if existing_dso.type is None:
                        existing_dso.type = dso_type
                    if existing_dso.constellation_id is None:
                        existing_dso.constellation_id = constellation_id
                    db.session.add(existing_dso)
                    db.session.flush()

                other_names = row['OTHER'].strip().split(';')

                other_ids = []
                if other_names:
                    for other_name in other_names:
                        other_name = normalize_dso_name(other_name)
                        if other_name.startswith('M'):
                            # Fix messier mag, SAC has exact value
                            other_dso = DeepskyObject.query.filter_by(name=other_name).first()
                            if other_dso:
                                other_dso.mag = mag
                                db.session.add(other_dso)
                                db.session.flush()
                        elif other_name.startswith('NGC') or other_name.startswith('Abell'):
                            other_dso = DeepskyObject.query.filter_by(name=other_name).first()
                            if other_dso:
                                other_ids.append(other_dso.id)
                        # create UGC records from NGC sysnoinymas
                        if create_synonymas and object_name.startswith('NGC') and other_name.startswith('UGC'):
                            if existing_dso:
                                catalogue_id = Catalogue.get_catalogue_id_by_cat_code('UGC')
                                c = DeepskyObject(
                                    name = other_name,
                                    type = existing_dso.type if existing_dso.type else dso_type,
                                    master_id = existing_dso.id,
                                    ra = existing_dso.ra,
                                    dec = existing_dso.dec,
                                    constellation_id = existing_dso.constellation_id if existing_dso.constellation_id else constellation_id,
                                    catalogue_id = catalogue_id,
                                    major_axis = existing_dso.major_axis,
                                    minor_axis =  existing_dso.minor_axis,
                                    positon_angle =  existing_dso.positon_angle,
                                    mag = mag,
                                    b_mag = existing_dso.b_mag,
                                    v_mag = existing_dso.v_mag,
                                    j_mag =  existing_dso.j_mag,
                                    h_mag =  existing_dso.h_mag,
                                    k_mag =  existing_dso.k_mag,
                                    surface_bright = existing_dso.surface_bright,
                                    hubble_type =  existing_dso.hubble_type,
                                    c_star_u_mag = existing_dso.c_star_u_mag,
                                    c_star_b_mag = existing_dso.c_star_b_mag,
                                    c_star_v_mag = existing_dso.c_star_v_mag,
                                    identifiers = existing_dso.identifiers,
                                    common_name = existing_dso.common_name,
                                    descr = row['NOTES'],
                                    )
                                db.session.add(c)
                                db.session.flush()

                if not existing_dso:
                    c = DeepskyObject(
                        name = object_name,
                        type = dso_type,
                        master_id = other_ids[0] if len(other_ids) > 0 else None,
                        ra = Angle(hours=tuple(map(float, row['RA'].split(' ')))).radians if len(row['RA']) > 0 else None,
                        dec = Angle(degrees=tuple(map(float, row['DEC'].split(' ')))).radians if len(row['DEC']) > 0 else None,
                        constellation_id = constellation_id,
                        catalogue_id = catalogue_id,
                        major_axis = get_size(row['SIZE_MAX']),
                        minor_axis =  get_size(row['SIZE_MIN']),
                        positon_angle =  None,
                        mag = mag,
                        b_mag = None,
                        v_mag = None,
                        j_mag =  None,
                        h_mag =  None,
                        k_mag =  None,
                        surface_bright = None,
                        hubble_type =  None,
                        c_star_u_mag = None,
                        c_star_b_mag = None,
                        c_star_v_mag = None,
                        identifiers = None,
                        common_name = None,
                        descr = row['NOTES'],
                        )
                    db.session.add(c)
                    db.session.flush()
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line
