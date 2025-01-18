from datetime import datetime
import base64

from flask import (
    abort,
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app.models import Constellation, StarList, StarListItem, StarListDescription, User, UserDsoDescription
from app.commons.dso_utils import CHART_STAR_PREFIX
from app.commons.search_utils import process_session_search
from app.commons.utils import get_lang_and_editor_user_from_request
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    common_ra_dec_dt_fsz_from_request,
)

from .star_list_forms import (
    SearchStarListForm,
)

from app.main.chart.chart_forms import ChartForm
from ... import csrf

main_star_list = Blueprint('main_star_list', __name__)


def _find_star_list(star_list_id):
    try:
        int_id = int(star_list_id)
        return StarList.query.filter_by(id=int_id).first()
    except ValueError:
        return StarList.query.filter_by(name=star_list_id).first()


@main_star_list.route('/star-lists-menu', methods=['GET'])
def star_lists_menu():
    star_lists = StarList.query.all()
    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
    return render_template('main/catalogue/star_list_menu.html', star_lists=star_lists, lang_code=lang)


@main_star_list.route('/star-list/<string:star_list_id>', methods=['GET','POST'])
@main_star_list.route('/star-list/<string:star_list_id>/info', methods=['GET','POST'])
def star_list_info(star_list_id):
    """View a star list info."""
    star_list = _find_star_list(star_list_id)
    if star_list is None:
        abort(404)

    search_form = SearchStarListForm()
    if search_form.season.data == 'All':
        search_form.season.data = None

    if not process_session_search([('star_list_season', search_form.season),]):
        return redirect(url_for('main_star_list.star_list_info', star_list_id=star_list_id, season=search_form.season.data))

    season = request.args.get('season', None)
    constell_ids = Constellation.get_season_constell_ids(season)

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)

    star_list_descr = StarListDescription.query.filter_by(star_list_id=star_list.id, lang_code=lang).first()

    star_list_items = []
    for star_list_item in star_list.star_list_items:
        if constell_ids is None or star_list_item.star.constellation_id in constell_ids:
            star_list_items.append(star_list_item)

    theme = request.args.get('theme', '')
    inverted_accordion = theme in ['dark', 'night']

    return render_template('main/catalogue/star_list_info.html', star_list=star_list, type='info', star_list_descr=star_list_descr, star_list_items=star_list_items,
                            season=season, search_form=search_form, inverted_accordion=inverted_accordion)


@main_star_list.route('/star-list/<string:star_list_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def star_list_chart(star_list_id):
    star_list = _find_star_list(star_list_id)
    if star_list is None:
        abort(404)

    form  = ChartForm()

    star_id = request.args.get('star_id')
    star_list_item = None
    if star_id and star_id.isdigit():
        istar_id = int(star_id)
        star_list_item = next((x for x in star_list.star_list_items if x.star.id == istar_id), None)

    if not star_list_item:
        star_list_item = StarListItem.query.filter_by(star_list_id=star_list.id, item_id=1).first()

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
    star_list_descr = StarListDescription.query.filter_by(star_list_id=star_list.id, lang_code=lang).first()

    common_ra_dec_dt_fsz_from_request(form,
                                   star_list_item.star.ra if star_list_item else 0,
                                   star_list_item.star.dec if star_list_item else 0)

    chart_control = common_prepare_chart_data(form)

    default_chart_iframe_url = None
    if star_list_item:
        default_chart_iframe_url = url_for('main_star.star_info', star_id=star_list_item.star_id,
                                           back='star_list', back_id=star_list.id, embed='fc', allow_back='true')
    return render_template('main/catalogue/star_list_info.html', fchart_form=form, type='chart', star_list=star_list, star_list_descr=star_list_descr,
                           chart_control=chart_control, default_chart_iframe_url=default_chart_iframe_url)


@main_star_list.route('/star-list/<string:star_list_id>/chart-pos-img', methods=['GET'])
def star_list_chart_pos_img(star_list_id):
    star_list = _find_star_list(star_list_id)
    if star_list is None:
        abort(404)

    star_list = StarList.query.filter_by(id=star_list.id).first()
    highlights_pos_list = [(x.star.ra, x.star.dec, CHART_STAR_PREFIX + str(x.star.id), x.star.get_name()) for x in star_list.star_list_items if star_list]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_star_list.route('/star-list/<string:star_list_id>/chart-legend-img', methods=['GET'])
def star_list_chart_legend_img(star_list_id):
    star_list = _find_star_list(star_list_id)
    if star_list is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None)
    return send_file(img_bytes, mimetype='image/png')


@main_star_list.route('/star-list/<string:star_list_id>/chart-pdf', methods=['GET'])
def star_list_chart_pdf(star_list_id):
    star_list = _find_star_list(star_list_id)
    if star_list is None:
        abort(404)

    star_list = StarList.query.filter_by(id=star_list.id).first()
    highlights_star_list = [ x.star for x in star_list.star_list_items if star_list ]

    img_bytes = common_chart_pdf_img(None, None, highlights_star_list=highlights_star_list)

    return send_file(img_bytes, mimetype='application/pdf')
