import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject
from .import_utils import progress

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

    row_count = sum(1 for line in open(sh2_data_file))

    with open(sh2_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        catalogue_id = Catalogue.get_catalogue_id('SH2')
        row_id = 0
        for row in reader:
            progress(row_id, row_count, 'Importing Sh2 catalogue')
            row_id += 1
            try:
                c = DeepSkyObject(
                    name = row['NAME'],
                    type = 'Neb',
                    ra = row['RA'],
                    dec = row['DEC'],
                    constellation_id = constell_dict.get(row['Constellation'].upper(), None),
                    catalogue_id = catalogue_id,
                    major_axis = float(row['SIZE']),
                    minor_axis =  float(row['SIZE']),
                    positon_angle =  None,
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
                    descr = None,
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