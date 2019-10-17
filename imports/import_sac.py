import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject
from skyfield.units import Angle

from app.commons.dso_utils import normalize_dso_name
from .import_utils import progress

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
        for row in reader:
            progress(row_id, row_count, 'Importing SAC catalogue')
            row_id += 1
            try:
                catalogue_id = None
                object_id = row['OBJECT'].strip()
                if object_id.startswith('Abell '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Abell')
                elif object_id.startswith('Cr '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Cr')
                elif object_id.startswith('Pal '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Pal')
                elif object_id.startswith('PK '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('PK')
                elif object_id.startswith('Stock '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Stock')
                elif object_id.startswith('UGC '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('UGC')
                elif object_id.startswith('Mel '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('Mel')
                elif object_id.startswith('LDN '):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('LDN')
                elif object_id.startswith('B') and (object_id[1]==' ' or object_id[1].isdigit()):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('B')

                if not catalogue_id:
                    continue

                object_id = normalize_dso_name(object_id)

                c = DeepSkyObject(
                    name = object_id,
                    type = row['TYPE'],
                    ra = Angle(hours=tuple(map(float, row['RA'].split(' ')))).radians if len(row['RA']) > 0 else None,
                    dec = Angle(degrees=tuple(map(float, row['DEC'].split(' ')))).radians if len(row['DEC']) > 0 else None,
                    constellation_id = constell_dict.get(row['CON'].upper(), None),
                    catalogue_id = catalogue_id,
                    major_axis = get_size(row['SIZE_MAX']),
                    minor_axis =  get_size(row['SIZE_MIN']),
                    positon_angle =  None,
                    b_mag = None,
                    v_mag = float(row['MAG']) if row['MAG'] else None,
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
                db.session.commit()
            except KeyError as err:
                print('\nKey error: {}'.format(err))
                db.session.rollback()
            except IntegrityError as err:
                print('\nIntegrity error {}'.format(err))
                db.session.rollback()
        print('') # finish on new line