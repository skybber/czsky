import re
from datetime import datetime

from flask_babel import lazy_gettext

from app import db

from app.models import (
    Location,
    DeepskyObject,
    WishListItem
)

from app.commons.openastronomylog import (
    OaldeepSkyDS,
    OaldeepSkyMS,
    parse,
)

from app.commons.search_sky_object_utils import search_double_star
from app.commons.dso_utils import normalize_dso_name_ext, denormalize_dso_name


def import_wishlist_items(wishlist, file):
    log_warn = []
    log_error = []

    oal_observations = parse(file, silence=True)

    oal_targets = oal_observations.get_targets()
    item_order = 0
    existing_dsos = set()
    existing_double_stars = set()
    for item in wishlist.wish_list_items:
        if item.dso_id is not None:
            existing_dsos.add(item.dso_id)
        elif item.double_star_id is not None:
            existing_double_stars.add(item.double_star_id)
        if item.order >= item_order:
            item_order = item.order + 1

    not_found_targets = []

    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            if isinstance(target, (OaldeepSkyDS, OaldeepSkyMS)):
                double_star = search_double_star(target.get_name())
                if double_star:
                    if double_star.id not in existing_double_stars:
                        existing_double_stars.add(double_star.id)
                        item = WishListItem(
                            wish_list_id=wishlist.id,
                            double_star_id=double_star.id,
                            order=item_order,
                            create_date=datetime.now(),
                            update_date=datetime.now(),
                        )
                        db.session.add(item)
                        wishlist.wish_list_items.append(item)
                        item_order += 1
                else:
                    not_found_targets.add(target.get_id())
                    log_error.append(lazy_gettext('Double star "{}" not found').format(target.get_name()))
            else:
                normalized_name = normalize_dso_name_ext(denormalize_dso_name(target.get_name()))
                m = re.search(r'^(NGC|IC)\d+([A-Z]|-[1-9])$', normalized_name)
                if m:
                    normalized_name = normalized_name[:m.start(2)].strip()
                dso = DeepskyObject.query.filter_by(name=normalized_name).first()
                if dso:
                    if dso.id not in existing_dsos:
                        existing_dsos.add(dso.id)
                        item = WishListItem(
                            wish_list_id=wishlist.id,
                            dso_id=dso.id,
                            order=item_order,
                            create_date=datetime.now(),
                            update_date=datetime.now(),
                        )
                        db.session.add(item)
                        wishlist.wish_list_items.append(item)
                        item_order += 1
                else:
                    not_found_targets.add(target.get_id())
                    log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

    return log_warn, log_error

