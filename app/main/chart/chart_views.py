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
)

from app.commons.auto_img_utils import get_dso_image_info, get_dso_image_info_with_imgdir

main_chart = Blueprint('main_chart', __name__)

@main_chart.route('/chart', methods=['GET', 'POST'])
def chart():
    """View a chart."""
    form  = ChartForm()

    chart_control = common_prepare_chart_data(form)

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

    return render_template('main/chart/chart.html', fchart_form=form, chart_control=chart_control,)

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


