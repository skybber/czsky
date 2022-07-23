from datetime import datetime
import base64

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from posix import wait

from app.models import Constellation, DoubleStarList, DoubleStarListItem, DoubleStarListDescription, User, UserDsoDescription
from app.commons.dso_utils import CHART_DOUBLE_STAR_PREFIX
from app.commons.search_utils import process_session_search
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

    if not process_session_search([('double_star_list_season', search_form.season),]):
        return redirect(url_for('main_double_star_list.double_star_list_info', double_star_list_id=double_star_list_id, season=search_form.season.data))

    season = request.args.get('season', None)

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)

    if season:
        constell_ids = set()
        for constell_id in db.session.query(Constellation.id).filter(Constellation.season==season):
            constell_ids.add(constell_id[0])
    else:
        constell_ids = None

    double_star_list_descr = DoubleStarListDescription.query.filter_by(double_star_list_id=double_star_list.id, lang_code=lang).first()

    double_star_list_items = []
    for double_star_list_item in double_star_list.double_star_list_items:
        if constell_ids is None or double_star_list_item.double_star.constellation_id in constell_ids:
            double_star_list_items.append(double_star_list_item)

    theme = request.args.get('theme', '')
    inverted_accordion = theme in ['dark', 'night']

    return render_template('main/catalogue/double_star_list_info.html', double_star_list=double_star_list, type='info', double_star_list_descr=double_star_list_descr, double_star_list_items=double_star_list_items,
                           season=season, search_form=search_form, inverted_accordion=inverted_accordion)


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart', methods=['GET', 'POST'])
def double_star_list_chart(double_star_list_id):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    form  = ChartForm()

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
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = double_star_list_item.double_star.ra_first if double_star_list_item else 0
            form.dec.data = double_star_list_item.double_star.dec_first if double_star_list_item else 0

    chart_control = common_prepare_chart_data(form)

    return render_template('main/catalogue/double_star_list_info.html', fchart_form=form, type='chart', double_star_list=double_star_list, double_star_list_descr=double_star_list_descr,
                           chart_control=chart_control)


@main_double_star_list.route('/double-star-list/<string:double_star_list_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def double_star_list_chart_pos_img(double_star_list_id, ra, dec):
    double_star_list = _find_double_star_list(double_star_list_id)
    if double_star_list is None:
        abort(404)

    double_star_list = DoubleStarList.query.filter_by(id=double_star_list.id).first()
    highlights_pos_list = [(x.double_star.ra_first, x.double_star.dec_first, CHART_DOUBLE_STAR_PREFIX + str(x.double_star.id)) for x in double_star_list.double_star_list_items if double_star_list]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_pos_list=highlights_pos_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


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

