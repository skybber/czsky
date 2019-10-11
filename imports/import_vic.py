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

def import_vic(vic_data_file):
    """Import data from VIC catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    row_count = sum(1 for line in open(vic_data_file))

    with open(vic_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        catalogue_id = Catalogue.get_catalogue_id('VIC')
        row_id = 0
        for row in reader:
            row_id += 1
            progress(row_id, row_count, 'Importing VIC catalogue')
            try:
#                 constellation = row['Const']
                constellation = None

                name = 'VIC' + (str(row_id) if row_id >= 10 else ('0' + str(row_id)))

                c = DeepSkyObject(
                    name = name,
                    type = 'AST',
                    ra = row['RA'].strip().replace(',', ':'),
                    dec = row['Dec'].strip().replace(',', ':'),
                    constellation_id = constell_dict[constellation] if constellation else None,
                    catalogue_id = catalogue_id,
                    major_axis = vic2int(row['length']) / 10,
                    minor_axis =  vic2int(row['width']) / 10,
                    positon_angle =  vic2int(row['orient']) / 10,
                    b_mag = None,
                    v_mag = vic2int(row['mag']) / 10,
                    j_mag =  None,
                    h_mag =  None,
                    k_mag =  None,
                    surface_bright = vic2int(row['brightness']) / 10,
                    hubble_type =  None,
                    c_star_u_mag = None,
                    c_star_b_mag = None,
                    c_star_v_mag = None,
                    identifiers = None,
                    common_name = row['name'].strip(),
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
