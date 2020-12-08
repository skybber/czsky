import glob
import os

from app.commons.img_dir_resolver import parse_inline_link, resolve_img_path_dir
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name

from app.models import DeepskyObject

from app import db

_ug_bl_dsos = None

def get_dso_image_info(dso_name):
    dso_file_name = dso_name + '.jpg'
    img_dir_def = resolve_img_path_dir(os.path.join('dso', dso_file_name))
    if img_dir_def[0]:
        return img_dir_def[0] + 'dso/' + dso_file_name, parse_inline_link(img_dir_def[1])
    return None

def get_dso_image_info_with_imgdir(dso_name):
    dso_file_name = dso_name + '.jpg'
    img_dir_def = resolve_img_path_dir(os.path.join('dso', dso_file_name))
    if img_dir_def[0]:
        return '$IMG_DIR/dso/' + dso_file_name, parse_inline_link(img_dir_def[1])
    return None


def get_ug_bl_dsos():
    global _ug_bl_dsos
    if not _ug_bl_dsos:
        ug_bl_dsos = {}
        files = [f for f in sorted(glob.glob('app/static/webassets-external/users/glahn/img/dso/*.jpg'))] + \
            [f for f in sorted(glob.glob('app/static/webassets-external/users/laville/img/dso/*.jpg'))]

        for f in files:
            base_name = os.path.basename(f)
            if base_name.endswith('.jpg'):
                dso_name = base_name[:-len('.jpg')]
                normalized_name = normalize_dso_name(denormalize_dso_name(dso_name))
                dso = DeepskyObject.query.filter_by(name=normalized_name).first()
                if dso:
                    db.session.expunge(dso)
                    if not dso.constellation_id in ug_bl_dsos:
                        ug_bl_dsos[dso.constellation_id] = {}
                    ug_bl_dsos[dso.constellation_id][dso.id] = dso

        _ug_bl_dsos = ug_bl_dsos
    return _ug_bl_dsos

