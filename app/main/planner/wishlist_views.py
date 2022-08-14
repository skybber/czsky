import os
import csv
from datetime import datetime
import base64

from werkzeug.utils import secure_filename

import numpy as np

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
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
from app.commons.search_utils import process_session_search
from app.commons.chart_generator import (
    common_chart_pdf_img,
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
    common_set_initial_ra_dec,
)

from .wishlist_forms import (
    AddToWishListForm,
    SearchWishListForm,
)

from app.main.chart.chart_forms import ChartForm

from app.commons.dso_utils import normalize_dso_name

main_wishlist = Blueprint('main_wishlist', __name__)


@main_wishlist.route('/wish-list', methods=['GET', 'POST'])
@main_wishlist.route('/wish-list/info', methods=['GET', 'POST'])
@login_required
def wish_list_info():
    """View wish list."""
    add_form = AddToWishListForm()

    search_form = SearchWishListForm()
    if search_form.season.data == 'All':
        search_form.season.data = None

    if not process_session_search([('wish_list_season', search_form.season),]):
        return redirect(url_for('main_wishlist.wish_list_info', season=search_form.season.data))

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

    return render_template('main/planner/wish_list.html',type='info', wish_list_items=wish_list_items, season=season, search_form=search_form, add_form=add_form)


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

    return redirect(url_for('main_wishlist.wish_list_info'))


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
    return redirect(url_for('main_wishlist.wish_list_info'))


@main_wishlist.route('/wish-list/chart', methods=['GET', 'POST'])
@login_required
def wish_list_chart():
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    if wish_list is None:
        abort(404)

    form = ChartForm()

    dso_id = request.args.get('dso_id')

    wish_list_item = None
    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        wish_list_item = next((x for x in wish_list.wish_list_items if x.deepskyObject.id == idso_id), None)

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            if wish_list_item:
                form.ra.data = wish_list_item.deepskyObject.ra
                form.dec.data = wish_list_item.deepskyObject.dec
            else:
                common_set_initial_ra_dec(form)

    if not wish_list_item:
        wish_list_item = wish_list.wish_list_items[0] if wish_list.wish_list_items else None

    chart_control = common_prepare_chart_data(form)

    if wish_list_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='wishlist', dso_id=wish_list_item.deepskyObject.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    return render_template('main/planner/wish_list.html', fchart_form=form, type='chart', wish_list=wish_list, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, )


@main_wishlist.route('/wish-list/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
@login_required
def  wish_list_chart_pos_img(ra, dec):
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    if wish_list is None:
        abort(404)

    highlights_dso_list = [ x.deepskyObject for x in wish_list.wish_list_items if wish_list.wish_list_items ]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_wishlist.route('/wish-list/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
@login_required
def wish_list_chart_legend_img(ra, dec):
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    if wish_list is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_wishlist.route('/wish-list/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def wish_list_chart_pdf(ra, dec):
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    if wish_list is None:
        abort(404)

    highlights_dso_list = [ x.deepskyObject for x in wish_list.wish_list_items if wish_list.wish_list_items ]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_dso_list=highlights_dso_list)

    return send_file(img_bytes, mimetype='application/pdf')
