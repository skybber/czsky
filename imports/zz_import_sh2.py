import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from skyfield.units import Angle

from .import_utils import progress

from app.commons.dso_utils import normalize_dso_name

def vic2int(s):
    s.lstrip('0')
    if len(s) == 0:
        return 0
    return int(s)

def import_sh2(sh2_data_file):
    """Import data from Sh2 catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.name.upper()] = co.id

    row_count = sum(1 for line in open(sh2_data_file)) - 1

    with open(sh2_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        catalogue_id = Catalogue.get_catalogue_id_by_cat_code('SH2')
        row_id = 0
        try:
            for row in reader:
                progress(row_id, row_count, 'Importing Sh2 catalogue')
                row_id += 1

                # dso_name = normalize_dso_name(row['NAME'])

                c = DeepskyObject.query.filter_by(name = dso_name).first()

                if c is None:
                    c = DeepskyObject()

                c.name = dso_name
                c.type = 'Neb'
                c.ra = Angle(hours=float(row['RA'])).radians if len(row['RA']) > 0 else None
                c.dec = Angle(degrees=float(row['RA'])).radians if len(row['RA']) > 0 else None
                c.constellation_id = constell_dict.get(row['Constellation'].upper(), None)
                c.catalogue_id = catalogue_id
                c.major_axis = float(row['SIZE']) * 60.0
                c.minor_axis =  float(row['SIZE']) * 60.0
                c.positon_angle =  None
                c.b_mag = None
                c.v_mag = None
                c.j_mag =  None
                c.h_mag =  None
                c.k_mag =  None
                c.surface_bright = None
                c.hubble_type =  None
                c.c_star_u_mag = None
                c.c_star_b_mag = None
                c.c_star_v_mag = None
                c.identifiers = None
                c.common_name = None
                c.descr = None

                db.session.add(c)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line