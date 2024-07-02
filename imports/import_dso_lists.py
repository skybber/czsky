import glob, os, csv
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import DeepskyListType
from app.models.dso_list import DsoList, DsoListDescription, DsoListItem
from app.models.user import User
from app.models.deepskyobject import DeepskyObject

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

        lang_code = descr_file[-(2+app_len):-app_len]

        dso_list_descr = DsoListDescription.query.filter_by(dso_list_id=dso_list.id, lang_code=lang_code).first()
        if dso_list_descr:
            dso_list_descr.long_name=lines[0]
            dso_list_descr.short_descr=lines[2]
            dso_list_descr.text='\n'.join(lines[4:])
            dso_list_descr.update_by=editor_user.id
            dso_list_descr.update_date=datetime.now()
        else:
            dso_list_descr = DsoListDescription(
                dso_list_id=dso_list.id,
                long_name=lines[0],
                short_descr=lines[2],
                lang_code = lang_code,
                text='\n'.join(lines[4:]),
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
            dso_list = DsoList.query.filter_by(name='Herschel400').first()
            if dso_list:
                dso_list.name = 'Herschel400'
                dso_list.long_name = 'Herschel400'
                dso_list.show_common_name = True
                dso_list.show_dso_type = True
                dso_list.show_angular_size = True
                dso_list.show_minor_axis = True
                dso_list.list_type = DeepskyListType.CLASSIC
                dso_list.update_by=editor_user.id
                dso_list.create_date=datetime.now()
                dso_list.dso_list_items[:] = []
                dso_list.dso_list_descriptions[:] = []
            else:
                dso_list = DsoList(
                    name='Herschel400',
                    long_name = 'Herschel400',
                    show_common_name = True,
                    show_dso_type = True,
                    show_angular_size = True,
                    show_minor_axis = True,
                    list_type = DeepskyListType.CLASSIC,
                    create_by=editor_user.id,
                    update_by=editor_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
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
                item = DsoListItem.query.filter_by(dso_list_id=dso_list.id, dso_id=dso.id).first()
                if not item:
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
            dso_list = DsoList.query.filter_by(name='Caldwell').first()
            if dso_list:
                dso_list.name ='Caldwell'
                dso_list.long_name ='Caldwell'
                dso_list.show_common_name = True
                dso_list.show_dso_type = True
                dso_list.show_angular_size = True
                dso_list.show_minor_axis = True
                dso_list.list_type = DeepskyListType.CLASSIC
                dso_list.update_by=editor_user.id
                dso_list.create_date=datetime.now()
                dso_list.dso_list_items[:] = []
                dso_list.dso_list_descriptions[:] = []
            else:
                dso_list = DsoList(
                    name='Caldwell',
                    long_name='Caldwell',
                    create_by=editor_user.id,
                    update_by=editor_user.id,
                    show_common_name = True,
                    show_dso_type = True,
                    show_angular_size = True,
                    show_minor_axis = True,
                    list_type = DeepskyListType.CLASSIC,
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

                item = DsoListItem.query.filter_by(dso_list_id=dso_list.id, dso_id=dso.id).first()
                if not item:
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


def _do_import_simple_csv(csv_data_file, dso_list_name, dso_list_long_name, list_type, show_common_name=True, show_dso_type=False,
                          show_angular_size=True, show_minor_axis=True, show_descr_name=False, hidden=False,
                          show_distance=False, distance_mult=0.0):
    row_count = sum(1 for line in open(csv_data_file)) - 1

    with open(csv_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            editor_user = User.get_editor_user()
            dso_list = DsoList.query.filter_by(name=dso_list_name).first()
            if dso_list:
                for item in dso_list.dso_list_items:
                    db.session.delete(item)
                dso_list.dso_list_items.clear()
                dso_list.name = dso_list_name
                dso_list.long_name = dso_list_long_name
                dso_list.show_common_name = show_common_name
                dso_list.show_descr_name = show_descr_name
                dso_list.list_type = list_type
                dso_list.update_by = editor_user.id
                dso_list.show_dso_type = show_dso_type
                dso_list.show_angular_size = show_angular_size
                dso_list.show_minor_axis = show_minor_axis
                dso_list.show_distance = show_distance
                dso_list.create_date = datetime.now()
                dso_list.dso_list_items[:] = []
                dso_list.dso_list_descriptions[:] = []
                dso_list.hidden = hidden
            else:
                dso_list = DsoList(
                    name=dso_list_name,
                    long_name=dso_list_long_name,
                    show_common_name=show_common_name,
                    show_descr_name=show_descr_name,
                    list_type=list_type,
                    create_by=editor_user.id,
                    update_by=editor_user.id,
                    show_dso_type=show_dso_type,
                    show_angular_size=show_angular_size,
                    show_minor_axis=show_minor_axis,
                    show_distance=show_distance,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                    hidden=hidden
                )

            db.session.add(dso_list)
            db.session.flush()

            base_name = os.path.basename(csv_data_file)
            descr_list = _load_descriptions(os.path.dirname(csv_data_file), base_name[:-len('.csv')], dso_list, editor_user)

            for descr in descr_list:
                db.session.add(descr)

            row_id = 0
            for row in reader:
                row_id += 1
                progress(row_id, row_count, 'Importing ' + dso_list_long_name + ' list')
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue

                object_name = dso_name.replace(' ', '')
                dso = DeepskyObject.query.filter_by(name=object_name).first()

                if not dso:
                    print('Not found: {}'.format(object_name))
                    continue

                if show_distance and dso.distance is None:
                    dso_distance = None
                    try:
                        dso_distance = float(row['DIST'])
                    except ValueError as err:
                        pass
                    if dso_distance is not None:
                        dso.distance = dso_distance * distance_mult
                        db.session.add(dso)

                item = DsoListItem.query.filter_by(dso_list_id=dso_list.id, dso_id=dso.id).first()
                if not item:
                    item = DsoListItem(
                        dso_list_id=dso_list.id,
                        dso_id=dso.id,
                        item_id=row_id,
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
    _do_import_simple_csv(superthingx_data_file, 'thin-glx', 'Superthin Galaxies', DeepskyListType.EXOTIC, show_common_name=False)


def import_holmberg(holmberg_data_file):
    _do_import_simple_csv(holmberg_data_file, 'holberg-glx', 'Galaxies from Holmberg catalog', DeepskyListType.EXOTIC, show_common_name=False)


def import_abell_pn(abell_pn_data_file):
    _do_import_simple_csv(abell_pn_data_file, 'abell-pn', 'Abell Catalog of Planetary Nebulae', DeepskyListType.TYPED, show_common_name=False, show_minor_axis=False)


def import_vic_list(vic_data_file):
    _do_import_simple_csv(vic_data_file, 'vic-aster', 'VIC list of asterism', DeepskyListType.CZSKY, show_angular_size=False, show_descr_name=True)


def import_rosse(rosse_data_file):
    _do_import_simple_csv(rosse_data_file, 'rosse-spirals', 'Rosse Spirals', DeepskyListType.EXOTIC, show_dso_type=True)


def import_glahn_pns(glahn_pn_data_file):
    _do_import_simple_csv(glahn_pn_data_file, 'glahn-pn', 'Planetary nebulas of northern hemisphere', DeepskyListType.TYPED, show_minor_axis=False)


def import_glahn_palomar_gc(glahn_palomar_gc_data_file):
    _do_import_simple_csv(
        glahn_palomar_gc_data_file, 'palomar-gc', 'Palomar globular clusters', DeepskyListType.TYPED, show_common_name=False, show_minor_axis=False)


def import_glahn_local_group(glahn_local_group_data_file):
    _do_import_simple_csv(
        glahn_local_group_data_file, 'local-group', 'Local group of galaxies', DeepskyListType.EXOTIC, show_minor_axis=False)


def import_corstjens(corstjens_file):
    _do_import_simple_csv(
        corstjens_file, 'corstjens', 'Tim Corstjens images', show_minor_axis=False, hidden=True)


def import_hickson(hickson_data_file):
    _do_import_simple_csv(hickson_data_file, 'hickson', 'Hickson Compact Group', DeepskyListType.TYPED, show_common_name=False, show_minor_axis=False)


def import_billionaries_club(billionaries_club_data_file):
    _do_import_simple_csv(
        billionaries_club_data_file, 'billionaries-club', 'Billionaries Club', DeepskyListType.EXOTIC, show_minor_axis=True, show_distance=True, distance_mult=1000000000.0)

def import_deep_man_600(deep_man_600_data_file):
    _do_import_simple_csv(
        deep_man_600_data_file, 'deep-man-600', 'Deep Man 600', DeepskyListType.CLASSIC, show_minor_axis=True, show_dso_type=True)

def import_minimistr_dn(minimistr_dn_data_file):
    _do_import_simple_csv(minimistr_dn_data_file, 'minimistr-dn', 'MiniMistr Dark Nebulae', DeepskyListType.CZSKY, show_minor_axis=False)
