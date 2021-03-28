import os
from datetime import datetime
import numpy as np
import base64

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
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
from app.commons.utils import get_lang_and_editor_user_from_request

from .chart_forms import (
    ChartForm,
)

from app.commons.chart_generator import (
    get_chart_legend_flags,
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_chart_dso_list_menu,
    MAG_SCALES,
    DSO_MAG_SCALES,
    STR_GUI_FIELD_SIZES
)

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
            day_zero = datetime(2021, 3, 21, 0, 0, 0).timetuple().tm_yday
            day_now = datetime.now().timetuple().tm_yday
            form.ra.data = 2.0 * np.pi * (day_now - day_zero) / 365 + np.pi
            if form.ra.data > 2 * np.pi:
                form.ra.data -= 2 * np.pi
        if form.dec.data is None:
            form.dec.data = 0.0

    night_mode = True

    return render_template('main/chart/chart.html', fchart_form=form,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           dso_mag_scale=cur_dso_mag_scale, disable_dso_dec_mag=disable_dso_dec_mag, disable_dso_inc_mag=disable_dso_inc_mag,
                           gui_field_sizes=STR_GUI_FIELD_SIZES, gui_field_index = (form.radius.data-1)*2,
                           chart_fsz=str(fld_size), chart_mlim=str(form.maglim.data), chart_dlim=str(form.dso_maglim.data), chart_nm=('1' if night_mode else '0'),
                           chart_mx=('1' if form.mirror_x.data else '0'), chart_my=('1' if form.mirror_y.data else '0'),
                           mag_ranges=MAG_SCALES, mag_range_values=mag_range_values, dso_mag_ranges=DSO_MAG_SCALES, dso_mag_range_values=dso_mag_range_values,
                           chart_flags=chart_flags, legend_flags=legend_flags, fchart_dso_list_menu=common_chart_dso_list_menu(),
                           )

@main_chart.route('/chart/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_pos_img(ra, dec):
    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')

@main_chart.route('/chart/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_legend_img(ra, dec):
    img_bytes = common_chart_legend_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='image/png')

@main_chart.route('/chart/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def chart_pdf(ra, dec):
    img_bytes = common_chart_pdf_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='application/pdf')


