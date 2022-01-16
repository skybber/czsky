import sys, os, glob
import numpy as np
from datetime import datetime

from app import db
from app.models.constellation import Constellation
from app.models.star import Star
from app.models.starlist import StarList, StarListDescription, StarListItem
from app.models.user import User
from skyfield.api import position_from_radec, load_constellation_map

from .import_utils import progress


def _load_descriptions(dirname, base_name, star_list, editor_user):
    result = []
    descr_files = [f for f in sorted(glob.glob(dirname + '/' + base_name + '_*.md'))]
    app_len = len('.md')
    for descr_file in descr_files:
        content = None
        with open(descr_file) as f:
            content = f.read()
        lines = content.splitlines()

        lang_code = descr_file[-(2+app_len):-app_len]

        star_list_descr = StarListDescription.query.filter_by(star_list_id=star_list.id, lang_code=lang_code).first()
        if star_list_descr:
            star_list_descr.long_name=lines[0]
            star_list_descr.short_descr=lines[2]
            star_list_descr.text='\n'.join(lines[4:])
            star_list_descr.update_by=editor_user.id
            star_list_descr.update_date=datetime.now()
        else:
            star_list_descr = StarListDescription(
                star_list_id=star_list.id,
                long_name=lines[0],
                short_descr=lines[2],
                lang_code=lang_code,
                text='\n'.join(lines[4:]),
                create_by= editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now(),
            )
        result.append(star_list_descr)
    return result


def import_carbon_stars(carbon_stars_data_file):
    sf = open(carbon_stars_data_file, 'r')
    lines = sf.readlines()
    sf.close()

    constellation_at = load_constellation_map()

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    try:
        editor_user = User.get_editor_user()
        star_list = StarList.query.filter_by(name='carbon-stars').first()
        if star_list:
            star_list.name='carbon-stars'
            star_list.long_name='Carbon Stars'
            star_list.update_by=editor_user.id
            star_list.create_date=datetime.now()
            star_list.star_list_items[:] = []
            star_list.star_list_descriptions[:] = []
        else:
            star_list = StarList(
                name='carbon-stars',
                long_name='Carbon Stars',
                create_by=editor_user.id,
                update_by=editor_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )

        db.session.add(star_list)
        db.session.flush()

        base_name = os.path.basename(carbon_stars_data_file)
        descr_list = _load_descriptions(os.path.dirname(carbon_stars_data_file), base_name[:-len('.txt')], star_list, editor_user)

        for descr in descr_list:
            db.session.add(descr)

        db.session.flush()

        row_count = len(lines)
        row_id = 0
        for line in lines:
            row_id += 1
            progress(row_id, row_count, 'Importing carbon stars catalog')
            str_hd = line[0:7].strip()
            hd = int(str_hd) if str_hd else None
            var_id = line[7:17].strip()
            ra = int(line[17:23].strip())*np.pi/12.0 + int(line[23:26].strip())*np.pi/(12.0*60.0) + float(line[26:31].strip())*np.pi/(12*60.0*60)
            dec = int(line[34:35] + '1') * (int(line[35:37].strip())*np.pi/180.0 + int(line[38:40].strip())*np.pi/(180.0 * 60.0) + int(line[41:43].strip())*np.pi/(180.0*60.0*60.0))
            mag = float(line[43:50].strip())
            sp_type = line[50:69].strip()
            max_min = line[69:82].strip()
            min = None
            max = None
            if max_min:
                sep_index = max_min.find('-')
                if sep_index >= 0:
                    min = float(max_min[0:sep_index])
                    max = float(max_min[sep_index+1:])

            star = None

            if hd is not None:
                star = Star.query.filter_by(hd=hd).first()

            if not star and var_id:
                star = Star.query.filter_by(var_id=var_id).first()

            if not star:
                star = Star()
                star.src_catalogue = 'carbon_stars'

            constellation = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))

            star.hd = hd
            star.var_id = var_id
            star.ra = ra
            star.dec = dec
            star.mag = mag
            star.mag_max = max
            star.mag_min = min
            star.constellation_id = constell_dict[constellation] if constellation else None
            if sp_type:
                star.sp_type = sp_type

            db.session.add(star)
            db.session.flush()

            item = StarListItem.query.filter_by(star_list_id=star_list.id, star_id = star.id).first()
            if not item:
                item = StarListItem(
                    star_list_id=star_list.id,
                    star_id=star.id,
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
