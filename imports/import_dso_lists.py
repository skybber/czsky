import glob, os, csv
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.dsolist import DsoList, DsoListDescription, DsoListItem
from app.models.user import User
from app.models.deepskyobject import DeepskyObject

from app.commons.dso_utils import normalize_dso_name
from .import_utils import progress

def _load_descriptions(dirname, base_name, dso_list, editor_user):
    result = []
    descr_files = [f for f in sorted(glob.glob(dirname + '/' + base_name + '_*.md'))]
    app_len = len('.md')
    for descr_file in descr_files:
        content = None
        with open(descr_file) as f:
            content = f.read()
        lines = content.splitlines()

        dso_list_descr = DsoListDescription(
            dso_list_id=dso_list.id,
            short_descr=lines[0],
            lang_code = descr_file[-(2+app_len):-app_len],
            text='\n'.join(lines[2:]),
            create_by= editor_user.id,
            update_by=editor_user.id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        result.append(dso_list_descr)
    return result


def import_herschel400(herschel400_data_file):

    row_count = sum(1 for line in open(herschel400_data_file)) - 1

    with open(herschel400_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            editor_user = User.get_editor_user()
            existing_dso_list = DsoList.query.filter_by(name='Herschel400').first()
            if existing_dso_list:
                db.session.delete(existing_dso_list)
                db.session.flush()

            dso_list = DsoList(
                name='Herschel400',
                create_by=editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )

            db.session.add(dso_list)
            db.session.flush()

            base_name = os.path.basename(herschel400_data_file)
            descr_list = _load_descriptions(os.path.dirname(herschel400_data_file), base_name[:-len('.csv')], dso_list, editor_user)

            for descr in descr_list:
                db.session.add(descr)

            row_id = 0
            for row in reader:
                row_id += 1
                progress(row_id, row_count, 'Importing Herschel400 list')

                dso_name = 'NGC' + row['NGC_ID']
                object_name = dso_name.replace(' ','')
                dso = DeepskyObject.query.filter_by(name=object_name).first()

                if dso is None:
                    print('Not found: {}'.format(object_name))
                    continue
                item = DsoListItem(
                    dso_list_id=dso_list.id,
                    dso_id = dso.id,
                    item_id = row_id,
                    create_by=editor_user.id,
                    create_date=datetime.now(),
                )
                db.session.add(item)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line

def import_caldwell(caldwell_data_file):

    row_count = sum(1 for line in open(caldwell_data_file)) - 1

    with open(caldwell_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            editor_user = User.get_editor_user()
            existing_dso_list = DsoList.query.filter_by(name='Caldwell').first()
            if existing_dso_list:
                db.session.delete(existing_dso_list)
                db.session.flush()

            dso_list = DsoList(
                name='Caldwell',
                create_by=editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )

            db.session.add(dso_list)
            db.session.flush()

            base_name = os.path.basename(caldwell_data_file)
            descr_list = _load_descriptions(os.path.dirname(caldwell_data_file), base_name[:-len('.csv')], dso_list, editor_user)

            for descr in descr_list:
                db.session.add(descr)

            row_id = 0
            for row in reader:
                row_id += 1
                progress(row_id, row_count, 'Importing Caldwell list')
                dso_name = row['DSO_ID']
                if dso_name == 'none':
                    continue
                object_name = dso_name.replace(' ', '')
                dso = DeepskyObject.query.filter_by(name=object_name).first()

                if not dso:
                    print('Not found: {}'.format(object_name))
                    continue

                item = DsoListItem(
                    dso_list_id=dso_list.id,
                    dso_id = dso.id,
                    item_id = int(row['ID']),
                    create_by=editor_user.id,
                    create_date=datetime.now(),
                )
                db.session.add(item)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line

def import_superthin_gx(superthingx_data_file):

    row_count = sum(1 for line in open(superthingx_data_file)) - 1

    with open(superthingx_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            editor_user = User.get_editor_user()
            existing_dso_list = DsoList.query.filter_by(name='Superthin Galaxies').first()
            if existing_dso_list:
                db.session.delete(existing_dso_list)
                db.session.flush()

            dso_list = DsoList(
                name='Superthin Galaxies',
                create_by=editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )

            db.session.add(dso_list)
            db.session.flush()

            base_name = os.path.basename(superthingx_data_file)
            descr_list = _load_descriptions(os.path.dirname(superthingx_data_file), base_name[:-len('.csv')], dso_list, editor_user)

            for descr in descr_list:
                db.session.add(descr)

            row_id = 0
            for row in reader:
                row_id += 1
                progress(row_id, row_count, 'Importing Superthin Galaxy list')
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue
                object_name = dso_name.replace(' ', '')
                dso = DeepskyObject.query.filter_by(name=object_name).first()

                if not dso:
                    print('Not found: {}'.format(object_name))
                    continue

                item = DsoListItem(
                    dso_list_id=dso_list.id,
                    dso_id = dso.id,
                    item_id = row_id,
                    create_by=editor_user.id,
                    create_date=datetime.now(),
                )
                db.session.add(item)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('') # finish on new line
