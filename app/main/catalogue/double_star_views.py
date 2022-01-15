from datetime import datetime
import os
import base64

from sqlalchemy import or_

from io import BytesIO

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import Constellation, DoubleStar, DoubleStarList
from app.commons.pagination import Pagination
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
)

from app.commons.utils import get_lang_and_editor_user_from_request
from app.commons.search_utils import process_paginated_session_search, get_items_per_page, create_table_sort

from app.main.chart.chart_forms import ChartForm

from .double_star_forms import SearchDoubleStarForm

main_double_star = Blueprint('main_double_star', __name__)


@main_double_star.route('/double-stars', methods=['GET', 'POST'])
def double_stars():
    """View double stars."""
    search_form = SearchDoubleStarForm()

    sort_by = request.args.get('sortby')

    ret, page = process_paginated_session_search('dbl_star_search_page', [
        ('dbl_star_search', search_form.q),
        ('dbl_mag_max', search_form.mag_max),
        ('dbl_delta_mag_min', search_form.delta_mag_min),
        ('dbl_separation_min', search_form.separation_min),
        ('dbl_separation_max', search_form.separation_max),
        ('dec_min', search_form.dec_min),
        ('items_per_page', search_form.items_per_page)
    ])

    if not ret:
        return redirect(url_for('main_double_star.double_stars', page=page, sortby=sort_by))

    per_page = get_items_per_page(search_form.items_per_page)

    offset = (page - 1) * per_page

    dbl_star_query = DoubleStar.query
    if search_form.q.data:
        dbl_star_query = dbl_star_query.filter(or_(DoubleStar.common_cat_id == search_form.q.data,
                                               DoubleStar.wds_number == search_form.q.data))
    else:
        if search_form.mag_max.data:
            dbl_star_query = dbl_star_query.filter(DoubleStar.mag_first < search_form.mag_max.data, DoubleStar.mag_second < search_form.mag_max.data)
        if search_form.delta_mag_min.data:
            dbl_star_query = dbl_star_query.filter(DoubleStar.delta_mag > search_form.delta_mag_min.data)
        if search_form.separation_min.data:
            dbl_star_query = dbl_star_query.filter(DoubleStar.separation > search_form.separation_min.data)
        if search_form.separation_max.data:
            dbl_star_query = dbl_star_query.filter(DoubleStar.separation < search_form.separation_max.data)
        if search_form.dec_min.data:
            dbl_star_query = dbl_star_query.filter(DoubleStar.dec_first > search_form.dec_min.data)

    sort_def = { 'wds_number': DoubleStar.wds_number,
                 'common_cat_id': DoubleStar.common_cat_id,
                 'components': DoubleStar.components,
                 'other_designation': DoubleStar.other_designation,
                 'ra': DoubleStar.ra_first,
                 'dec': DoubleStar.dec_first,
                 'mag_first': DoubleStar.mag_first,
                 'mag_second': DoubleStar.mag_second,
                 'separation': DoubleStar.separation,
                 'spectral_type': DoubleStar.spectral_type,
                 'constellation': DoubleStar.constellation_id,
                 }

    table_sort = create_table_sort(sort_by, sort_def.keys())

    order_by_field = None
    if sort_by:
        desc = sort_by[0] == '-'
        sort_by_name = sort_by[1:] if desc else sort_by
        order_by_field = sort_def.get(sort_by_name)
        if order_by_field and desc:
            order_by_field = order_by_field.desc()

    if order_by_field is None:
        order_by_field = DoubleStar.id

    shown_double_stars = dbl_star_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=dbl_star_query.count(), search=False, record_name='double_stars',
                            css_framework='semantic', not_passed_args='back')

    return render_template('main/catalogue/double_stars.html', double_stars=shown_double_stars, pagination=pagination,
                           search_form=search_form, table_sort=table_sort)


@main_double_star.route('/double-star/<int:double_star_id>/catalogue-data')
def double_star_catalogue_data(double_star_id):
    """View a double star catalogue data."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'catalogue_data'

    season = request.args.get('season')

    prev_dbl_star, next_dbl_star = _get_prev_next_double_star(double_star)

    return render_template('main/catalogue/double_star_info.html', type='catalogue_data', double_star=double_star,
                           embed=embed, prev_dbl_star=prev_dbl_star, next_dbl_star=next_dbl_star, season=season, )


@main_double_star.route('/double-star/<int:double_star_id>/chart', methods=['GET', 'POST'])
def double_star_chart(double_star_id):
    """View a double star findchart."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if not double_star:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'catalogue_data'

    season = request.args.get('season')

    form = ChartForm()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = double_star.ra_first
            form.dec.data = double_star.dec_first

    chart_control = common_prepare_chart_data(form)

    prev_dbl_star, next_dbl_star = _get_prev_next_double_star(double_star)

    return render_template('main/catalogue/double_star_info.html', fchart_form=form, type='chart', double_star=double_star,
                           chart_control=chart_control, prev_dbl_star=prev_dbl_star, next_dbl_star=next_dbl_star, embed=embed, season=season, )


@main_double_star.route('/double-star/<string:double_star_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def double_star_chart_pos_img(double_star_id, ra, dec):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(double_star.ra_first, double_star.dec_first, ra, dec, visible_objects=visible_objects)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_double_star.route('/double-star/<string:double_star_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def double_star_chart_legend_img(double_star_id, ra, dec):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    img_bytes = common_chart_legend_img(double_star.ra_first, double_star.dec_first, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_double_star.route('/double-star/<string:double_star_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def double_star_chart_pdf(double_star_id, ra, dec):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    img_bytes = common_chart_pdf_img(double_star.ra_first, double_star.dec_first, ra, dec)

    return send_file(img_bytes, mimetype='application/pdf')


def _get_season_constell_ids():
    season = request.args.get('season', None)
    if season is not None:
        constell_ids = set()
        for constell_id in db.session.query(Constellation.id).filter(Constellation.season==season):
            constell_ids.add(constell_id[0])
        return constell_ids
    return None


def _get_prev_next_double_star(star):
    back = request.args.get('back')
    back_id = request.args.get('back_id')

    if back == 'observation':
        pass # TODO
    elif back == 'wishlist':
        pass # TODO
    elif back == 'observed_list':
        pass # TODO
    elif back == 'session_plan':
        pass # TODO
    elif back == 'double_star_list' and not (back_id is None):
        double_star_list = DoubleStarList.query.filter_by(id=back_id).first()
        if double_star_list:
            prev_item, next_item = double_star_list.get_prev_next_item(star.id, _get_season_constell_ids())
            return prev_item.double_star if prev_item else None, next_item.double_star if next_item else None

    return None, None
