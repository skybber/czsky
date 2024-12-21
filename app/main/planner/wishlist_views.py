import base64
import csv
import os
from io import StringIO, BytesIO
import codecs

from sqlalchemy.orm import joinedload

from werkzeug.utils import secure_filename

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

from flask_babel import gettext

from app import db, csrf

from app.models import (
    Constellation,
    DeepskyObject,
    WishList,
    WishListItem,
)

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

from app.commons.dso_utils import normalize_dso_name, CHART_DOUBLE_STAR_PREFIX
from app.commons.prevnext_utils import find_by_url_obj_id_in_list, get_default_chart_iframe_url
from app.commons.highlights_list_utils import common_highlights_from_wishlist_items, find_wish_list_observed
from app.commons.search_sky_object_utils import search_double_star, search_dso
from .wishlist_export import create_oal_observations_from_wishlist
from .wishlist_import import import_wishlist_items

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
    constell_ids = Constellation.get_season_constell_ids(season)

    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    wish_list_items = []

    if constell_ids:
        for item in wish_list.wish_list_items:
            if item.deepsky_object and item.deepsky_object.constellation_id in constell_ids:
                wish_list_items.append(item)
    else:
        wish_list_items = wish_list.wish_list_items

    return render_template('main/planner/wish_list.html',type='info', wish_list_items=wish_list_items, season=season, search_form=search_form, add_form=add_form)


@main_wishlist.route('/wish-list-item-add', methods=['POST'])
@login_required
def wish_list_item_add():
    """Add item to wish list."""
    form = AddToWishListForm()
    if request.method == 'POST' and form.validate_on_submit():
        query = form.object_id.data.strip()
        double_star, deepsky_object = None, None
        double_star = search_double_star(query, number_search=False)
        if not double_star:
            deepsky_object = search_dso(query)

        if double_star or deepsky_object:
            wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
            new_item = None
            if double_star:
                if not wish_list.find_double_star_by_id(double_star.id):
                    new_item = wish_list.create_new_double_star_item(double_star.id)
            else:
                if not wish_list.find_dso_by_id(deepsky_object.id):
                    new_item = wish_list.create_new_deepsky_object_item(deepsky_object.id)
            if new_item:
                db.session.add(new_item)
                db.session.commit()
                flash('Object was added to wishlist.', 'form-success')
            else:
                flash('Object is already on wishlist.', 'form-info')
        else:
            flash('Object not found.', 'form-error')

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


@main_wishlist.route('/wish-list/import', methods=['POST'])
@login_required
def wish_list_import():
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    if 'file' not in request.files:
        flash(gettext('No file part'), 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash(gettext('No file selected'))
        return redirect(request.url)
    if file:
        is_oal = file.filename.lower().endswith('oal')
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        if is_oal:
            with open(path) as oalfile:
                log_warn, log_error = import_wishlist_items(wish_list, oalfile)
            db.session.commit()
            flash(gettext('Wish list uploaded.'), 'form-success')
        else:
            with open(path) as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['DSO_NAME'])
                existing_ids = set(item.dso_id for item in wish_list.wish_list_items)

                for row in reader:
                    dso_name = row['DSO_NAME']
                    if dso_name == 'none':
                        continue

                    dso_name = normalize_dso_name(dso_name)
                    dso = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()

                    if dso and dso.id not in existing_ids:
                        if not wish_list.find_dso_by_id(dso.id):
                            new_item = wish_list.create_new_deepsky_object_item(dso.id)
                            db.session.add(new_item)
                        existing_ids.add(dso.id)
                db.session.commit()
                os.remove(path)
                flash(gettext('Wishlist uploaded.'), 'form-success')

    session['is_backr'] = True
    return redirect(url_for('main_wishlist.wish_list_info'))


@main_wishlist.route('/wish-list/export-csv', methods=['POST'])
@login_required
def wish_list_export_csv():
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    buf = StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_NONNUMERIC, delimiter=';')

    writer.writerow([gettext('Name'), gettext('Type'), gettext('Constellation'), 'RA', 'DEC'])

    for item in wish_list.wish_list_items:
        name = None
        if item.dso_id is not None:
            dso = item.deepsky_object
            name = dso.denormalized_name() + (('/' + dso.master_dso.denormalized_name()) if dso.master_dso else '')
            constell_iau_code = dso.get_constellation_iau_code()
            ra, dec = dso.ra_str_short(), dso.dec_str_short()
            type = 'DSO'
        elif item.double_star_id is not None:
            double_star = item.double_star
            name = double_star.get_common_norm_name()
            constell_iau_code = double_star.get_constellation_iau_code()
            ra, dec = double_star.ra_first_str_short(), double_star.dec_first_str_short()
            type = 'DBL_STAR'

        if name is not None:
            writer.writerow([name, type, constell_iau_code, ra, dec])


    mem = BytesIO()
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name='wishlist.csv', mimetype='text/csv')


@main_wishlist.route('/wish-list/export-oal', methods=['POST'])
@login_required
def wish_list_export_oal():
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    buf = StringIO()
    buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
    oal_observations = create_oal_observations_from_wishlist(current_user, wish_list)
    oal_observations.export(buf, 0)
    mem = BytesIO()
    mem.write(codecs.BOM_UTF8)
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)

    return send_file(mem, as_attachment=True, download_name='wishlist.oal', mimetype='text/xml')


@main_wishlist.route('/wish-list/clear', methods=['GET'])
@login_required
def wishlist_clear():
    """Request for clear of a wish list items."""
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)

    WishListItem.query.filter_by(wish_list_id=wish_list.id).delete()
    db.session.commit()
    flash(gettext('Wishlist items deleted'), 'form-success')
    session['is_backr'] = True
    return redirect(url_for('main_wishlist.wish_list_info'))


@main_wishlist.route('/wish-list/chart', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def wish_list_chart():
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    if wish_list is None:
        abort(404)

    form = ChartForm()

    wish_list_item = find_by_url_obj_id_in_list(request.args.get('obj_id'), wish_list.wish_list_items)

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            if wish_list_item:
                form.ra.data = wish_list_item.get_ra()
                form.dec.data = wish_list_item.get_dec()
            else:
                common_set_initial_ra_dec(form)

    if not wish_list_item:
        wish_list_item = wish_list.wish_list_items[0] if wish_list.wish_list_items else None

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(wish_list_item, back='wishlist')

    return render_template('main/planner/wish_list.html', fchart_form=form, type='chart', wish_list=wish_list, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, )


@main_wishlist.route('/wish-list/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
@login_required
def wish_list_chart_pos_img(ra, dec):
    wish_list = WishList.query.filter_by(user_id=current_user.id).first()
    wish_list_items = _get_wish_list_items(wish_list)
    highlights_dso_list, highlights_pos_list = common_highlights_from_wishlist_items(wish_list_items)
    flags = request.args.get('json')
    visible_objects = [] if flags else None
    observed_dso_ids = find_wish_list_observed(wish_list)
    img_bytes, img_format = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list,
                                                 observed_dso_ids=observed_dso_ids)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


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
    wish_list = WishList.query.filter_by(user_id=current_user.id).first()
    wish_list_items = _get_wish_list_items(wish_list)
    highlights_dso_list, highlights_pos_list = common_highlights_from_wishlist_items(wish_list_items)
    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')


def _get_wish_list_items(wish_list):
    if wish_list:
        return db.session.query(WishListItem).options(joinedload(WishListItem.deepsky_object)) \
            .filter(WishListItem.wish_list_id == wish_list.id) \
            .all()
    return []


def common_highlights_from_wishlist_items(wish_list_items):
    highlights_dso_list = []
    highlights_pos_list = []

    if wish_list_items:
        for item in wish_list_items:
            if item.dso_id is not None:
                highlights_dso_list.append(item.deepsky_object)
            elif item.double_star_id is not None:
                highlights_pos_list.append([item.double_star.ra_first, item.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(item.double_star_id), item.double_star.get_common_name()])
    return highlights_dso_list, highlights_pos_list
