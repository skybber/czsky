import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject,DsoCatalogueLink

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
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        print('Importing VIC catalog ...')
        catal_id = catal_dict['VIC'].id
        for row in reader:
            try:
                sys.stdout.write('.')
                sys.stdout.flush()
                constellation = row['Const']

                vic_id = row['Vic#'].strip()
                if len(vic_id) < 2:
                    vic_id = '0' + vic_id
                name = 'VIC' + vic_id
                c = DeepSkyObject(
                    name = name,
                    type = 'AST',
                    ra = row['RA'].strip(),
                    dec = row['Dec'].strip(),
                    constellation_id = constell_dict[constellation] if constellation else None,
                    major_axis =  None,
                    minor_axis =  None,
                    positon_angle =  None,
                    b_mag = None,
                    v_mag = None,
                    j_mag =  None,
                    h_mag =  None,
                    k_mag =  None,
                    surface_bright =  None,
                    hubble_type =  None,
                    c_star_u_mag = None,
                    c_star_b_mag = None,
                    c_star_v_mag = None,
                    identifiers = None,
                    common_name = row['en_name'].strip(),
                    descr = row['Note'].strip(),
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
