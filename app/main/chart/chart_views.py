import os

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
    jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db

from app.models import (
    Catalogue,
    Constellation,
    DeepskyObject,
    DsoList,
    ObservedList,
    ObservedListItem,
    SHOWN_APERTURE_DESCRIPTIONS,
    SessionPlan,
    SkyList,
    User,
    UserDsoApertureDescription,
    UserDsoDescription,
    WishList,
    WishListItem,
)
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
from app.commons.search_utils import process_paginated_session_search
from app.commons.utils import get_lang_and_editor_user_from_request

from .chart_forms import (
    ChartForm,
)

from app.main.views import ITEMS_PER_PAGE
from app.commons.chart_generator import get_chart_legend_flags, common_chart_pos_img, common_chart_legend_img, common_prepare_chart_data, MAG_SCALES, DSO_MAG_SCALES, STR_GUI_FIELD_SIZES
from app.commons.auto_img_utils import get_dso_image_info, get_dso_image_info_with_imgdir

main_chart = Blueprint('main_chart', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 15/60, 30/60, 1, 2, 5, 10)

@main_chart.route('/chart', methods=['GET', 'POST'])
def chart():
    """View a chart."""
    form  = ChartForm()

    fld_size, cur_mag_scale, cur_dso_mag_scale, mag_range_values, dso_mag_range_values = common_prepare_chart_data(form)

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    disable_dso_dec_mag = 'disabled' if form.dso_maglim.data <= cur_dso_mag_scale[0] else ''
    disable_dso_inc_mag = 'disabled' if form.dso_maglim.data >= cur_dso_mag_scale[1] else ''

    chart_flags, legend_flags = get_chart_legend_flags(form)

    ra = request.args.get('ra', None)
    dec = request.args.get('dec', None)
    if ra is not None and dec is not None:
        form.ra.data = float(ra)
        form.dec.data = float(dec)
    else:
        if form.ra.data is None:
            form.ra.data = 0.0
        if form.dec.data is None:
            form.dec.data = 0.0

    night_mode = not session.get('themlight', False)

    return render_template('main/chart/chart.html', form=form,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           dso_mag_scale=cur_dso_mag_scale, disable_dso_dec_mag=disable_dso_dec_mag, disable_dso_inc_mag=disable_dso_inc_mag,
                           gui_field_sizes=STR_GUI_FIELD_SIZES, gui_field_index = (form.radius.data-1)*2,
                           chart_fsz=str(fld_size), chart_mlim=str(form.maglim.data), chart_dlim=str(form.dso_maglim.data), chart_nm=('1' if night_mode else '0'),
                           chart_mx=('1' if form.mirror_x.data else '0'), chart_my=('1' if form.mirror_y.data else '0'),
                           mag_ranges=MAG_SCALES, mag_range_values=mag_range_values, dso_mag_ranges=DSO_MAG_SCALES, dso_mag_range_values=dso_mag_range_values,
                           chart_flags=chart_flags, legend_flags=legend_flags,
                           )


@main_chart.route('/chart/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_pos_img(ra, dec):
    img_bytes = common_chart_pos_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='image/png')


@main_chart.route('/chart/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_legend_img(ra, dec):
    img_bytes = common_chart_legend_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='image/png')
