import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject

def import_abell(abell_data_file):
    """Import data from Abell catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    with open(abell_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        print('Importing Abell catalog of planetary nebula...')
        catalogue_id = Catalogue.get_catalogue_id('ABELL')
        for row in reader:
            try:
                sys.stdout.write('.')
                sys.stdout.flush()
                constellation = row['Const']

                if not row['Other'] or row['Other'] in ['platefault', 'galaxy', 'CTB1']:
                    continue

                mag = row['Mag']
                if mag and mag.endswith('p'):
                    mag = mag[:-1]

                cstar_mag = row['Cstar V-Mag']
                if cstar_mag == 'na':
                    cstar_mag = None

                c = DeepSkyObject(
                    name = 'ABELL' + row['Abell'],
                    type = 'PN', # TODO: row['Type'] is PN subtype ?
                    ra = row['RA'].replace(' ', ':'),
                    dec = row['Dec'].replace(' ', ':'),
                    constellation_id = constell_dict[constellation] if constellation else None,
                    catalogue_id = catalogue_id,
                    major_axis = float(row['MajAx']) if row['MajAx'] else None,
                    minor_axis = float(row['MinAx']) if row['MinAx'] else None,
                    positon_angle = None,
                    b_mag = None,
                    v_mag = mag,
                    j_mag = None,
                    h_mag = None,
                    k_mag = None,
                    surface_bright = None,
                    hubble_type =  None,
                    c_star_u_mag = None,
                    c_star_v_mag = float(cstar_mag) if cstar_mag else None,
                    identifiers = row['Other'],
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
