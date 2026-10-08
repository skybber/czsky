import base64

from flask import (
    abort,
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
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
from app.commons.chart_scene import (
    build_cross_highlight,
    build_scene_v1,
    build_stars_zones_v1,
    build_milkyway_catalog_v1,
    build_milkyway_select_v1,
    build_dso_outlines_catalog_v1,
    build_constellation_lines_catalog_v1,
    build_constellation_boundaries_catalog_v1,
)
from app.commons.coordinates import ra_to_str, dec_to_str
from app.commons.simbad_utils import simbad_query, SIMBAD_OTYPE_DESCRIPTIONS
from app.commons.utils import is_splitview_supported
from app.models import Constellation
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
    if not common_ra_dec_dt_fsz_from_request(form):
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


@main_chart.route('/chart/scene-v1', methods=['GET'])
def chart_scene_v1():
    return jsonify(build_scene_v1())


@main_chart.route('/chart/stars-v1/zones', methods=['GET'])
def chart_stars_zones_v1():
    return jsonify(build_stars_zones_v1())


@main_chart.route('/chart/milkyway-v1/catalog', methods=['GET'])
def chart_milkyway_catalog_v1():
    return jsonify(build_milkyway_catalog_v1())


@main_chart.route('/chart/milkyway-v1/select', methods=['GET'])
def chart_milkyway_select_v1():
    return jsonify(build_milkyway_select_v1())


@main_chart.route('/chart/dso-outlines-v1/catalog', methods=['GET'])
def chart_dso_outlines_catalog_v1():
    return jsonify(build_dso_outlines_catalog_v1())


@main_chart.route('/chart/constellation-lines-v1/catalog', methods=['GET'])
def chart_constellation_lines_catalog_v1():
    return jsonify(build_constellation_lines_catalog_v1())


@main_chart.route('/chart/constellation-boundaries-v1/catalog', methods=['GET'])
def chart_constellation_boundaries_catalog_v1():
    return jsonify(build_constellation_boundaries_catalog_v1())


@main_chart.route('/chart/chart-pdf', methods=['GET', 'POST'])
@csrf.exempt
def chart_pdf():
    img_bytes = common_chart_pdf_img(None, None)
    return send_file(img_bytes, mimetype='application/pdf')


def _get_simbad_obj_or_404():
    simbad_id = request.args.get('sid', '').strip()
    if not simbad_id:
        abort(404)
    simbad_obj = simbad_query(simbad_id)
    if simbad_obj is None:
        abort(404)
    return simbad_obj


@main_chart.route('/chart/simbad', methods=['GET', 'POST'])
@csrf.exempt
def simbad_object_chart():
    """View a chart of an object found in Simbad only (not present in the db)."""
    simbad_obj = _get_simbad_obj_or_404()

    if (
        request.method == 'GET'
        and not request.args.get('embed')
        and not request.args.get('fullscreen')
        and not request.args.get('splitview')
        and is_splitview_supported()
    ):
        args = request.args.to_dict(flat=True)
        args['splitview'] = 'true'
        return redirect(url_for('main_chart.simbad_object_chart', **args))

    form = ChartForm()
    common_ra_dec_dt_fsz_from_request(form, simbad_obj['ra'], simbad_obj['dec'], 60)
    chart_control = common_prepare_chart_data(form)

    default_chart_iframe_url = url_for('main_chart.simbad_object_info', sid=simbad_obj['main_id'], embed='fc')

    return render_template('main/chart/simbad_object_info.html', type='chart', simbad_obj=simbad_obj,
                           fchart_form=form, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, embed=request.args.get('embed'))


@main_chart.route('/chart/simbad/info', methods=['GET'])
def simbad_object_info():
    """View info of an object found in Simbad only."""
    simbad_obj = _get_simbad_obj_or_404()

    constellation = Constellation.get_constellation_by_position(simbad_obj['ra'], simbad_obj['dec'])

    return render_template('main/chart/simbad_object_info.html', type='info', simbad_obj=simbad_obj,
                           otype_descr=SIMBAD_OTYPE_DESCRIPTIONS.get(simbad_obj['otype']),
                           constellation=constellation,
                           ra_str=ra_to_str(simbad_obj['ra']), dec_str=dec_to_str(simbad_obj['dec']),
                           embed=request.args.get('embed'))


@main_chart.route('/chart/simbad/chart-pos-img', methods=['GET'])
def simbad_object_chart_pos_img():
    simbad_obj = _get_simbad_obj_or_404()

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(simbad_obj['ra'], simbad_obj['dec'], visible_objects=visible_objects)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_chart.route('/chart/simbad/scene-v1', methods=['GET'])
def simbad_object_chart_scene_v1():
    simbad_obj = _get_simbad_obj_or_404()

    scene = build_scene_v1()
    scene_objects = scene.setdefault('objects', {})
    highlights = scene_objects.setdefault('highlights', [])
    highlights.append(
        build_cross_highlight(
            highlight_id=simbad_obj['main_id'],
            label=simbad_obj['main_id'],
            ra=simbad_obj['ra'],
            dec=simbad_obj['dec'],
            theme_name=session.get('theme'),
        )
    )
    return jsonify(scene)


@main_chart.route('/chart/simbad/chart-pdf', methods=['GET', 'POST'])
@csrf.exempt
def simbad_object_chart_pdf():
    simbad_obj = _get_simbad_obj_or_404()
    img_bytes = common_chart_pdf_img(simbad_obj['ra'], simbad_obj['dec'])
    return send_file(img_bytes, mimetype='application/pdf')
