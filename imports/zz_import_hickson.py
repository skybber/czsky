import sys
import numpy as np

from app import db
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from skyfield.units import Angle
from app.commons.dso_utils import normalize_dso_name

from .import_utils import progress

def import_hickson(hcg_data_file):
    """Import data from HCG catalog."""
    from sqlalchemy.exc import IntegrityError

    sf = open(hcg_data_file, 'r')
    lines = sf.readlines()
    sf.close()

    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('HCG')

    row_id = 0;

    try:
        for line in lines:
            row_id += 1
            progress(row_id, len(lines), 'Importing HCG catalogue')
            hcg_id = int(line[0:3])
            ra = float(line[4:6])*np.pi/12.0 + float(line[7:11])*np.pi/(12.0*60.0)
            dec = float(line[12]+'1')*float(line[13:17])*np.pi/180.0
            mag = float(line[18:22])
            other = line[23:45].strip()

            dso_name = 'HCG' + str(hcg_id)

            c = DeepskyObject.query.filter_by(name = dso_name).first()

            if c is None:
                c = DeepskyObject()

            c.name = dso_name
            c.type = 'GGroup'
            c.ra = ra
            c.dec = dec
            c.constellation_id = None
            c.catalogue_id = catalogue_id
            c.major_axis = None
            c.minor_axis =  None
            c.positon_angle =  None
            c.mag = mag
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
            c.descr = other

            db.session.add(c)
        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line