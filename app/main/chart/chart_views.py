import base64

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .chart_forms import (
    ChartForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
    common_set_initial_celestial_position,
    set_chart_session_param,
    set_horiz_from_equatorial,
)
from ... import csrf

main_chart = Blueprint('main_chart', __name__)


@main_chart.route('/chart-fullscreen', methods=['GET'])
@csrf.exempt
def chart_fullscreen():
    """View a fullscreen chart."""
    return redirect(url_for('main_chart.chart', fullscreen='true'))


@main_chart.route('/chart-param', methods=['POST'])
@csrf.exempt
def chart_param():
    data = request.json

    if not data or not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'Invalid input. Expected JSON object.'}), 400

    result = {'status': 'success', 'message': 'Session values set.'}
    res_data = {}
    for key, value in data.items():
        item = set_chart_session_param(key, value)
        if item is not None:
            res_data.update(item)

    result['data'] = res_data

    return jsonify(result)


@main_chart.route('/chart', methods=['GET', 'POST'])
@csrf.exempt
def chart():
    """View a chart."""
    form = ChartForm()

    ra = request.args.get('mra', None)
    dec = request.args.get('mdec', None)
    if ra is not None and dec is not None:
        form.ra.data = float(ra)
        form.dec.data = float(dec)
    elif not common_ra_dec_dt_fsz_from_request(form):
        common_set_initial_celestial_position(form)
    set_horiz_from_equatorial(form)

    chart_control = common_prepare_chart_data(form)

    return render_template('main/chart/chart.html', fchart_form=form, chart_control=chart_control, mark_ra=ra, mark_dec=dec)


@main_chart.route('/chart/chart-pos-img', methods=['GET'])
def chart_pos_img():
    flags = request.args.get('json')

    mark_ra = request.args.get('mra', None)
    mark_dec = request.args.get('mdec', None)
    if mark_ra is not None and mark_dec is not None:
        f_mark_ra = float(mark_ra)
        f_mark_dec = float(mark_dec)
    else:
        f_mark_ra, f_mark_dec = None, None

    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(f_mark_ra, f_mark_dec, visible_objects=visible_objects)

    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_chart.route('/chart/chart-legend-img', methods=['GET'])
def chart_legend_img():
    img_bytes = common_chart_legend_img()
    return send_file(img_bytes, mimetype='image/png')


@main_chart.route('/chart/chart-pdf', methods=['GET'])
def chart_pdf():
    img_bytes = common_chart_pdf_img(None, None)
    return send_file(img_bytes, mimetype='application/pdf')
