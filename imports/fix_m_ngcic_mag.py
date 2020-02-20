import csv
import sys

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject

from app.commons.dso_utils import normalize_dso_name
from .import_utils import progress

def fix_ngcic_mag_from_sac(sac_data_file):
    """Fix ngcic magnitude from Saguaro astronomy club catalog."""
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
                progress(row_id, row_count, 'Fixing mag catalogue')
                row_id += 1
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
                elif object_name.startswith('IC'):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('IC')
                else:
                    continue

                object_name = normalize_dso_name(object_name)

                mag = row['MAG'].strip()
                if mag.endswith('p'):
                    mag = mag[:-1]

                dso = DeepskyObject.query.filter_by(name=object_name).first()
                if not dso:
                    print('Skipping not found dso {} '.format(object_name))
                    continue

                dso.mag = mag
                db.session.add(dso)

                other_names = row['OTHER'].strip().split(';')

                if other_names:
                    for other_name in other_names:
                        other_name = normalize_dso_name(other_name)
                        if other_name.startswith('M'):
                            other_dso = DeepskyObject.query.filter_by(name=other_name).first()
                            if other_dso:
                                other_dso.mag = mag
                                db.session.add(other_dso)

                db.session.flush()
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line