import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject,DsoCatalogueLink

def vic2int(s):
    s.lstrip('0')
    if len(s) == 0:
        return 0
    return int(s)

def import_vic(open_ngc_data_file):
    """Import data from VIC catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    catal_dict = {}

    for ca in Catalogue.query.all():
        catal_dict[ca.code] = ca

    with open(open_ngc_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        print('Importing VIC catalog ...')
        catal_id = catal_dict['VIC'].id
        row_id = 0
        for row in reader:
            row_id += 1
            try:
                sys.stdout.write('.')
                sys.stdout.flush()

#                 constellation = row['Const']
                constellation = None

                name = 'VIC' + (str(row_id) if row_id >= 10 else ('0' + str(row_id)))

                print (name)

                c = DeepSkyObject(
                    name = name,
                    type = 'AST',
                    ra = row['RA'].strip().replace(',', ':'),
                    dec = row['Dec'].strip().replace(',', ':'),
                    constellation_id = constell_dict[constellation] if constellation else None,
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
                db.session.flush()
                if catal_id:
                    l = DsoCatalogueLink(
                        catalogue_id = catal_dict['VIC'].id,
                        dso_id = c.id,
                        name = name
                        )
                    db.session.add(l)
                db.session.flush()
                db.session.commit()
            except KeyError as err:
                print('\nKey error: {}'.format(err))
                db.session.rollback()
            except IntegrityError as err:
                print('\nIntegrity error {}'.format(err))
                db.session.rollback()
        print('') # finish on new line
