import csv
import sys
import numpy as np

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from skyfield.units import Angle
from skyfield.api import position_from_radec, load_constellation_map

from .import_utils import progress


def vic2int(s):
    s.lstrip('0')
    if len(s) == 0:
        return 0
    return int(s)


def import_vic(vic_data_file):
    """Import data from VIC catalog."""
    from sqlalchemy.exc import IntegrityError

    constellation_at = load_constellation_map()

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    row_count = sum(1 for line in open(vic_data_file)) - 1

    with open(vic_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        catalogue_id = Catalogue.get_catalogue_id_by_cat_code('VIC')
        row_id = 0
        try:
            for row in reader:
                row_id += 1
                progress(row_id, row_count, 'Importing VIC catalogue')

                dso_name = 'VIC' + str(row_id)

                c = DeepskyObject.query.filter_by(name = dso_name).first()

                if c is None:
                    c = DeepskyObject()

                ra_ang = Angle(hours=tuple(map(float, row['RA'].split(',')))) if len(row['RA']) > 0 else None
                dec_ang = Angle(degrees=tuple(map(float, row['Dec'].split(',')))) if len(row['Dec']) > 0 else None

                constellation = constellation_at(position_from_radec(ra_ang.radians / np.pi * 12.0, dec_ang.radians / np.pi * 180.0))

                c.name = dso_name
                c.type = 'AST'
                c.ra = ra_ang.radians if ra_ang else None
                c.dec = dec_ang.radians if dec_ang else None
                c.constellation_id = constell_dict[constellation] if constellation else None
                c.catalogue_id = catalogue_id
                c.major_axis = vic2int(row['length']) / 10 * 60.0
                c.minor_axis =  vic2int(row['width']) / 10 * 60.0
                c.positon_angle =  vic2int(row['orient']) / 10
                c.mag = vic2int(row['mag']) / 10
                c.surface_bright = vic2int(row['brightness']) / 10
                c.hubble_type =  None
                c.c_star_u_mag = None
                c.c_star_b_mag = None
                c.c_star_v_mag = None
                c.identifiers = None
                c.common_name = row['name'].strip()
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
