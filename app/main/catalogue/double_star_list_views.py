import base64

import numpy as np
from sqlalchemy import or_

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from flask_login import current_user

from app.models import (
    Constellation,
    DoubleStar,
    DoubleStarList,
    DoubleStarListItem,
    DoubleStarListDescription,
    ObservedList,
    SessionPlan,
    UserDoubleStarDescription,
    WishList,
)

from app.commons.dso_utils import CHART_DOUBLE_STAR_PREFIX
from app.commons.utils import get_lang_and_editor_user_from_request
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    common_ra_dec_fsz_from_request,
)

from .double_star_list_forms import (
    SearchDoubleStarListForm,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.search_utils import (
    process_paginated_session_search,
    create_table_sort,
)
from ... import csrf

main_double_star_list = Blueprint('main_double_star_list', __name__)


def _find_double_star_list(double_star_list_id):
    try:
        int_id = int(double_star_list_id)
        return DoubleStarList.query.filter_by(id=int_id).first()
    except ValueError:
        return DoubleStarList.query.filter_by(name=double_star_list_id).first()


@main_double_star_list.route('/double-star-lists-menu', methods=['GET'])
def double_star_lists_menu():
    double_star_lists = DoubleStarList.query.all()
    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
    return render_template('main/catalogue/double_star_list_menu.html', double_star_lists=double_star_lists, lang_code=lang)

@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/seltab')
def double_star_list_seltab(double_star_list_id):
    """View a double star list seltab."""
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    if double_star_list.has_detail_view:
        return redirect(url_for('main_double_star_list.double_star_list_detail', double_star_list_id=double_star_list_id))

    return redirect(url_for('main_double_star_list.double_star_list_info', double_star_list_id=double_star_list_id))


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/detail', methods=['GET','POST'])
def double_star_list_detail(double_star_list_id):
    """View a double star list detail."""
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)

    double_star_list_descr = DoubleStarListDescription.query.filter_by(double_star_list_id=double_star_list.id, lang_code=lang).first()

    user_descrs = {}
    for item in double_star_list.double_star_list_items:
        ud = UserDoubleStarDescription.query.filter_by(double_star_id=item.double_star_id, user_id=editor_user.id, lang_code=lang).first()
        if ud:
            user_descrs[item.double_star_id] = ud

    wish_list = None
    observed_list = None
    offered_session_plans = None
    if current_user.is_authenticated:
        wish_list = [item.double_star_id for item in WishList.create_get_wishlist_by_user_id(current_user.id).wish_list_items]
        observed_list = [item.double_star_id for item in ObservedList.create_get_observed_list_by_user_id(current_user.id).observed_list_items]
        offered_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False).all()
    else:
        session_plan_id = session.get('session_plan_id')
        if session_plan_id:
            offered_session_plans = SessionPlan.query.filter_by(id=session_plan_id).all()

    return render_template('main/catalogue/double_star_list_info.html', double_star_list=double_star_list, type='detail',
                           double_star_list_descr=double_star_list_descr, user_descrs=user_descrs,
                           wish_list=wish_list, observed_list=observed_list, offered_session_plans=offered_session_plans, )

@main_double_star_list.route('/double-star-list/<string:double_star_list_id>', methods=['GET','POST'])
@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/info', methods=['GET','POST'])
def double_star_list_info(double_star_list_id):
    """View a double star list info."""
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    search_form = SearchDoubleStarListForm()

    if search_form.season.data == 'All':
        search_form.season.data = None

    ret, page, sort_by = process_paginated_session_search('dbl_star_list_search_page', 'dbl_list_sort_by', [
        ('dbl_star_search', search_form.q),
        ('dbl_list_season', search_form.season),
        ('dbl_list_mag_max', search_form.mag_max),
        ('dbl_list_delta_mag_min', search_form.delta_mag_min),
        ('dbl_list_delta_mag_max', search_form.delta_mag_max),
        ('dbl_list_separation_min', search_form.separation_min),
        ('dbl_list_separation_max', search_form.separation_max),
        ('dec_list_min', search_form.dec_min),
    ])

    if not ret:
        return redirect(url_for('main_double_star_list.double_star_list_info', double_star_list_id=double_star_list_id, sortby=sort_by))

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)

    dbl_list_query = DoubleStarListItem.query.filter(DoubleStarListItem.double_star_list_id == double_star_list.id) \
        .join(DoubleStarListItem.double_star)

    if search_form.q.data:
        dbl_list_query = dbl_list_query.filter(or_(DoubleStar.common_cat_id == search_form.q.data,
                                                   DoubleStar.wds_number == search_form.q.data.strip(),
                                                   DoubleStar.norm_other_designation.like('%;' + search_form.q.data.strip() + ';%')
                                                   ))
    else:
        if search_form.mag_max.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.mag_first < search_form.mag_max.data, DoubleStar.mag_second < search_form.mag_max.data)
        if search_form.delta_mag_min.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.delta_mag > search_form.delta_mag_min.data)
        if search_form.delta_mag_max.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.delta_mag < search_form.delta_mag_max.data)
        if search_form.separation_min.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.separation > search_form.separation_min.data)
        if search_form.separation_max.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.separation < search_form.separation_max.data)
        if search_form.dec_min.data is not None:
            dbl_list_query = dbl_list_query.filter(DoubleStar.dec_first > (np.pi * search_form.dec_min.data / 180.0))

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

    sel_double_star_list_items = dbl_list_query.order_by(order_by_field).all()

    constell_ids = Constellation.get_season_constell_ids(search_form.season.data)

    double_star_list_descr = DoubleStarListDescription.query.filter_by(double_star_list_id=double_star_list.id, lang_code=lang).first()

    double_star_list_items = []
    for double_star_list_item in sel_double_star_list_items:
        if constell_ids is None or double_star_list_item.double_star.constellation_id in constell_ids:
            double_star_list_items.append(double_star_list_item)

    theme = request.args.get('theme', '')
    inverted_accordion = theme in ['dark', 'night']

    return render_template('main/catalogue/double_star_list_info.html', double_star_list=double_star_list, type='info',
                           double_star_list_descr=double_star_list_descr, double_star_list_items=double_star_list_items,
                           search_form=search_form, inverted_accordion=inverted_accordion, table_sort=table_sort)


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def double_star_list_chart(double_star_list_id):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    form = ChartForm()

    star_id = request.args.get('star_id')
    double_star_list_item = None
    if star_id and star_id.isdigit():
        istar_id = int(star_id)
        double_star_list_item = next((x for x in double_star_list.double_star_list_items if x.double_star.id == istar_id), None)

    if not double_star_list_item:
        double_star_list_item = DoubleStarListItem.query.filter_by(double_star_list_id=double_star_list.id, item_id=1).first()

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
    double_star_list_descr = DoubleStarListDescription.query.filter_by(double_star_list_id=double_star_list.id, lang_code=lang).first()

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            form.ra.data = double_star_list_item.double_star.ra_first if double_star_list_item else 0
            form.dec.data = double_star_list_item.double_star.dec_first if double_star_list_item else 0

    default_chart_iframe_url = None
    if double_star_list_item:
        default_chart_iframe_url = url_for('main_double_star.double_star_info', double_star_id=double_star_list_item.double_star_id,
                                           back='dbl_star_list', back_id=double_star_list.id, embed='fc', allow_back='true')

    chart_control = common_prepare_chart_data(form)

    return render_template('main/catalogue/double_star_list_info.html', fchart_form=form, type='chart', double_star_list=double_star_list,
                           double_star_list_descr=double_star_list_descr, chart_control=chart_control, default_chart_iframe_url=default_chart_iframe_url,)


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def double_star_list_chart_pos_img(double_star_list_id, ra, dec):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    double_star_list = DoubleStarList.query.filter_by(id=double_star_list.id).first()
    highlights_pos_list = [(x.double_star.ra_first, x.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(x.double_star.id),
                            x.double_star.get_common_name()) for x in double_star_list.double_star_list_items if double_star_list]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def double_star_list_chart_legend_img(double_star_list_id, ra, dec):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def double_star_list_chart_pdf(double_star_list_id, ra, dec):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    double_star_list = DoubleStarList.query.filter_by(id=double_star_list.id).first()
    highlights_double_star_list = [ x.double_star for x in double_star_list.double_star_list_items if double_star_list ]

    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_double_star_list=highlights_double_star_list)

    return send_file(img_bytes, mimetype='application/pdf')
