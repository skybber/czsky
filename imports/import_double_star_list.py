import sys, os, glob
import numpy as np
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.constellation import Constellation
from app.models.double_star import DoubleStar
from app.models.double_star_list import DoubleStarList, DoubleStarListDescription, DoubleStarListItem
from app.models.user import User
from skyfield.api import position_from_radec, load_constellation_map

from .import_utils import progress


def _load_descriptions(dirname, base_name, double_star_list, editor_user):
    result = []
    descr_files = [f for f in sorted(glob.glob(dirname + '/' + base_name + '_*.md'))]
    app_len = len('.md')
    for descr_file in descr_files:
        content = None
        with open(descr_file) as f:
            content = f.read()
        lines = content.splitlines()

        lang_code = descr_file[-(2+app_len):-app_len]

        double_star_list_descr = DoubleStarListDescription.query.filter_by(double_star_list_id=double_star_list.id, lang_code=lang_code).first()
        if double_star_list_descr:
            double_star_list_descr.long_name = lines[0]
            double_star_list_descr.short_descr = lines[2]
            double_star_list_descr.text = '\n'.join(lines[4:])
            double_star_list_descr.update_by = editor_user.id
            double_star_list_descr.update_date = datetime.now()
        else:
            double_star_list_descr = DoubleStarListDescription(
                double_star_list_id=double_star_list.id,
                long_name=lines[0],
                short_descr=lines[2],
                lang_code=lang_code,
                text='\n'.join(lines[4:]),
                create_by= editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now(),
            )
        result.append(double_star_list_descr)
    return result

def import_double_star_list(dbl_star_data_file, list_name, description, by_wds):
    sf = open(dbl_star_data_file, 'r')
    lines = sf.readlines()
    sf.close()

    try:
        editor_user = User.get_editor_user()
        double_star_list = DoubleStarList.query.filter_by(name=list_name).first()
        if double_star_list:
            double_star_list.name = list_name
            double_star_list.long_name = description
            double_star_list.update_by = editor_user.id
            double_star_list.create_date = datetime.now()
            double_star_list.double_star_list_items[:] = []
            double_star_list.double_star_list_descriptions[:] = []
        else:
            double_star_list = DoubleStarList(
                name=list_name,
                long_name=description,
                create_by=editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )

        db.session.add(double_star_list)
        db.session.flush()


        base_name = os.path.basename(dbl_star_data_file)
        descr_list = _load_descriptions(os.path.dirname(dbl_star_data_file), base_name[:-len('.txt')], double_star_list, editor_user)

        for descr in descr_list:
            db.session.add(descr)

        db.session.flush()

        row_count = len(lines)
        row_id = 0
        for line in lines:
            row_id += 1
            progress(row_id, row_count, 'Importing {} double star list'.format(list_name))

            if by_wds:
                double_star = DoubleStar.query.filter_by(wds_number=line.strip()).first()

                if double_star:
                    item = DoubleStarListItem.query.filter_by(double_star_list_id=double_star_list.id, double_star_id=double_star.id).first()
                    if not item:
                        item = DoubleStarListItem(
                            double_star_list_id=double_star_list.id,
                            double_star_id=double_star.id,
                            item_id=row_id,
                            create_by=editor_user.id,
                            create_date=datetime.now(),
                        )
                    db.session.add(item)
                else:
                    print('Double star wds={} not found'.format(line.strip()))
            else:
                double_star = DoubleStar.query.filter_by(common_cat_id=line.strip()).first()

                if double_star:
                    item = DoubleStarListItem.query.filter_by(double_star_list_id=double_star_list.id, double_star_id=double_star.id).first()
                    if not item:
                        item = DoubleStarListItem(
                            double_star_list_id=double_star_list.id,
                            double_star_id=double_star.id,
                            item_id=row_id,
                            create_by=editor_user.id,
                            create_date=datetime.now(),
                        )
                    db.session.add(item)
                else:
                    print('Double star common_cat_id={} not found'.format(line.strip()))

        db.session.commit()

    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line

def import_herschel500(herschel500_data_file):
    import_double_star_list(herschel500_data_file, 'Herschel500', 'The Herschel 500 Double Stars', True)

def import_dmichalko(dmichalko_data_file):
    import_double_star_list(dmichalko_data_file, 'DMichalko', 'The David1 Double Stars', False)
