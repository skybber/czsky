from __future__ import annotations

from sqlalchemy import func

from app.commons.auto_img_utils import get_dso_image_info_with_imgdir
from app.commons.utils import get_lang_and_all_editor_users_from_request
from app.models import DeepskyObject, UserDsoApertureDescription, UserDsoDescription


def get_dso_descriptions(dso):
    lang, all_editor_users = get_lang_and_all_editor_users_from_request(for_constell_descr=False)
    user_descr = None
    apert_descriptions = []
    title_img = None
    if all_editor_users:
        used_apert_classes = set()
        for editor_user in all_editor_users:
            if not user_descr:
                check_udescr = UserDsoDescription.query.filter_by(
                    dso_id=dso.id,
                    user_id=editor_user.id,
                    lang_code=lang,
                ).first()
                if check_udescr and (check_udescr.text or check_udescr.common_name):
                    user_descr = check_udescr
            user_apert_descrs = (
                UserDsoApertureDescription.query.filter_by(
                    dso_id=dso.id,
                    user_id=editor_user.id,
                    lang_code=lang,
                )
                .filter(func.coalesce(UserDsoApertureDescription.text, "") != "")
                .order_by(
                    UserDsoApertureDescription.aperture_class,
                    UserDsoApertureDescription.lang_code,
                )
            )
            for apdescr in user_apert_descrs:
                if apdescr.aperture_class not in used_apert_classes:
                    if apdescr.aperture_class not in [cl[0] for cl in apert_descriptions] and apdescr.text:
                        if apdescr.aperture_class == "<100":
                            apert_descriptions.insert(0, (apdescr.aperture_class, apdescr.text))
                        else:
                            apert_descriptions.append((apdescr.aperture_class, apdescr.text))
                        used_apert_classes.add(apdescr.aperture_class)

        if not user_descr or not user_descr.text or not user_descr.text.startswith("![<]($IMG_DIR/"):
            image_info = get_dso_image_info_with_imgdir(dso.normalized_name_for_img())
            if image_info is not None:
                title_img = image_info[0]
    return user_descr, apert_descriptions, title_img


def get_dso_descriptions_with_master_fallback(dso):
    user_descr, apert_descriptions, title_img = get_dso_descriptions(dso)
    if (user_descr or apert_descriptions or title_img) or not dso.master_id:
        return user_descr, apert_descriptions, title_img

    master_dso = DeepskyObject.query.filter_by(id=dso.master_id).first()
    if not master_dso:
        return user_descr, apert_descriptions, title_img

    return get_dso_descriptions(master_dso)
