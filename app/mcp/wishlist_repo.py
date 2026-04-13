from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import or_
from sqlalchemy.orm import joinedload


def load_wishlist_items_for_user(user_id: int, *, get_app: Callable[[], Any]):
    from app.models import WishList, WishListItem

    app = get_app()
    with app.app_context():
        wish_list = WishList.query.filter_by(user_id=user_id).first()
        if not wish_list:
            return None, []

        wish_list_items = (
            WishListItem.query
            .options(joinedload(WishListItem.deepsky_object), joinedload(WishListItem.double_star))
            .filter_by(wish_list_id=wish_list.id)
            .all()
        )
        return wish_list, wish_list_items


def load_observed_sets_for_user_wishlist(
    user_id: int,
    wish_list_id: int,
    *,
    get_app: Callable[[], Any],
) -> tuple[set[int], set[int]]:
    from app import db
    from app.models import DeepskyObject, ObservedList, ObservedListItem, WishListItem

    app = get_app()
    with app.app_context():
        observed_dso_subquery = (
            db.session.query(ObservedListItem.dso_id)
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == user_id)
            .filter(ObservedListItem.dso_id.is_not(None))
        )

        observed_wishlist_dso_rows = (
            db.session.query(WishListItem.dso_id)
            .join(WishListItem.deepsky_object)
            .filter(WishListItem.wish_list_id == wish_list_id)
            .filter(
                or_(
                    WishListItem.dso_id.in_(observed_dso_subquery),
                    DeepskyObject.master_id.in_(observed_dso_subquery),
                )
            )
            .all()
        )
        observed_wishlist_dso_ids = {
            row[0] for row in observed_wishlist_dso_rows if row and row[0] is not None
        }

        observed_double_star_rows = (
            db.session.query(ObservedListItem.double_star_id)
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == user_id)
            .filter(ObservedListItem.double_star_id.is_not(None))
            .all()
        )
        observed_double_star_ids = {
            row[0] for row in observed_double_star_rows if row and row[0] is not None
        }

    return observed_wishlist_dso_ids, observed_double_star_ids
