import os
import csv
from datetime import datetime

from werkzeug.utils import secure_filename

import numpy as np

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import (
    Constellation,
    DeepskyObject,
    WishList,
    WishListItem,
)

from app.commons.pagination import Pagination, get_page_parameter
from app.commons.search_utils import process_session_search, process_paginated_session_search, get_items_per_page, create_table_sort, get_catalogues_menu_items

from .wishlist_forms import (
    AddToWishListForm,
    SearchWishListForm,
)

from app.commons.dso_utils import normalize_dso_name

main_wishlist = Blueprint('main_wishlist', __name__)

@main_wishlist.route('/wish-list', methods=['GET', 'POST'])
@login_required
def wish_list():
    """View wish list."""
    add_form = AddToWishListForm()

    search_form = SearchWishListForm()
    if search_form.season.data == 'All':
        search_form.season.data = None

    if not process_session_search([('wish_list_season', search_form.season),]):
        return redirect(url_for('main_wishlist.wish_list', season=search_form.season.data))

    season = request.args.get('season', None)

    if season:
        constell_ids = set()
        for constell_id in db.session.query(Constellation.id).filter(Constellation.season==season):
            constell_ids.add(constell_id[0])
    else:
        constell_ids = None

    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    wish_list_items = []

    if constell_ids:
        for item in wish_list.wish_list_items:
            if item.deepskyObject and item.deepskyObject.constellation_id in constell_ids:
                wish_list_items.append(item)
    else:
        wish_list_items = wish_list.wish_list_items

    return render_template('main/planner/wish_list.html', wish_list_items=wish_list_items, season=season, search_form=search_form, add_form=add_form)


@main_wishlist.route('/wish-list-item-add', methods=['POST'])
@login_required
def wish_list_item_add():
    """Add item to wish list."""
    form = AddToWishListForm()
    dso_name = normalize_dso_name(form.dso_name.data)
    if request.method == 'POST' and form.validate_on_submit():
        deepsky_object = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()
        if deepsky_object:
            wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
            if wish_list.append_deepsky_object(deepsky_object.id, current_user.id):
                flash('Object was added to wishlist.', 'form-success')
            else:
                flash('Object is already on wishlist.', 'form-info')
        else:
            flash('Deepsky object not found.', 'form-error')

    return redirect(url_for('main_wishlist.wish_list'))


@main_wishlist.route('/wish-list-item/<int:item_id>/delete')
@login_required
def wish_list_item_remove(item_id):
    """Remove item to wish list."""
    wish_list_item = WishListItem.query.filter_by(id=item_id).first()
    if wish_list_item is None:
        abort(404)
    if wish_list_item.wish_list.user_id != current_user.id:
        abort(404)
    db.session.delete(wish_list_item)
    flash('Wishlist item was deleted', 'form-success')
    return redirect(url_for('main_wishlist.wish_list'))
