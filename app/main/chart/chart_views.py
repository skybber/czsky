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
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_chart_dso_list_menu,
    common_ra_dec_fsz_from_request,
    common_set_initial_ra_dec,
)

from app.commons.auto_img_utils import get_dso_image_info, get_dso_image_info_with_imgdir

main_chart = Blueprint('main_chart', __name__)


@main_chart.route('/chart', methods=['GET', 'POST'])
def chart():
    """View a chart."""
    form = ChartForm()

    ra = request.args.get('mra', None)
    dec = request.args.get('mdec', None)
    if ra is not None and dec is not None:
        form.ra.data = float(ra)
        form.dec.data = float(dec)
    elif not common_ra_dec_fsz_from_request(form):
        common_set_initial_ra_dec(form)

    chart_control = common_prepare_chart_data(form)

    return render_template('main/chart/chart.html', fchart_form=form, chart_control=chart_control, mark_ra=ra, mark_dec=dec)


@main_chart.route('/chart/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_pos_img(ra, dec):
    flags = request.args.get('json')

    mark_ra = request.args.get('mra', None)
    mark_dec = request.args.get('mdec', None)
    if mark_ra is not None and mark_dec is not None:
        f_mark_ra = float(mark_ra)
        f_mark_dec = float(mark_dec)
    else:
        f_mark_ra, f_mark_dec = None, None

    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(f_mark_ra, f_mark_dec, ra, dec, visible_objects=visible_objects)

    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_chart.route('/chart/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def chart_legend_img(ra, dec):
    img_bytes = common_chart_legend_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='image/png')


@main_chart.route('/chart/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def chart_pdf(ra, dec):
    img_bytes = common_chart_pdf_img(None, None, ra, dec)
    return send_file(img_bytes, mimetype='application/pdf')
