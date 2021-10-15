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
from sqlalchemy.orm import subqueryload

from app import db
from posix import wait

from app.models import Constellation, DsoList, DsoListItem, DsoListDescription, User, UserDsoDescription, StarList, ObservedList, ObservedListItem
from app.commons.search_utils import process_session_search
from app.commons.utils import get_lang_and_editor_user_from_request
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    common_ra_dec_fsz_from_request,
)

from .dso_list_forms import (
    SearchDsoListForm,
)

from app.main.chart.chart_forms import ChartForm

main_dso_list = Blueprint('main_dso_list', __name__)


highlights_dso_list_cache = { }


def _find_dso_list(dso_list_id):
    try:
        int_id = int(dso_list_id)
        return DsoList.query.filter_by(id=int_id).first()
    except ValueError:
        return DsoList.query.filter_by(name=dso_list_id).first()


def _find_highlights_dso_list(dso_list_id):
    ret = highlights_dso_list_cache.get(dso_list_id)
    if not ret:
        dso_list = _find_dso_list(dso_list_id)
        if dso_list:
            ret = []
            for item in dso_list.dso_list_items:
                dso = item.deepskyObject
                db.session.expunge(dso)
                ret.append(dso)
            highlights_dso_list_cache[dso_list_id] = ret
    return ret


@main_dso_list.route('/dso-lists-menu', methods=['GET'])
def dso_lists_menu():
    dso_lists = DsoList.query.all()
    star_lists = StarList.query.all()
    lang, editor_user = get_lang_and_editor_user_from_request()
    return render_template('main/catalogue/dso_list_menu.html', dso_lists=dso_lists, star_lists=star_lists, lang_code=lang)


@main_dso_list.route('/dso-list/<string:dso_list_id>', methods=['GET','POST'])
@main_dso_list.route('/dso-list/<string:dso_list_id>/info', methods=['GET','POST'])
def dso_list_info(dso_list_id):
    """View a dso list info."""
    dso_list = _find_dso_list(dso_list_id)
    if dso_list is None:
        abort(404)

    search_form = SearchDsoListForm()
    if search_form.season.data == 'All':
        search_form.season.data = None

    if not process_session_search([('dso_list_season', search_form.season),]):
        return redirect(url_for('main_dso_list.dso_list_info', dso_list_id=dso_list_id, season=search_form.season.data))

    season = request.args.get('season', None)

    lang, editor_user = get_lang_and_editor_user_from_request()

    if season:
        constell_ids = set()
        for constell_id in db.session.query(Constellation.id).filter(Constellation.season==season):
            constell_ids.add(constell_id[0])
    else:
        constell_ids = None

    dso_list_descr = DsoListDescription.query.filter_by(dso_list_id=dso_list.id, lang_code=lang).first()

    observed = { dso.id for dso in ObservedList.get_observed_dsos_by_user_id(current_user.id) } if not current_user.is_anonymous else None

    user_descrs = {} if dso_list.show_descr_name else None
    dso_list_items = []
    for dso_list_item in dso_list.dso_list_items:
        if constell_ids is None or dso_list_item.deepskyObject.constellation_id in constell_ids:
            dso_list_items.append(dso_list_item)
            if not user_descrs is None:
                udd =   UserDsoDescription.query.filter_by(dso_id=dso_list_item.dso_id, user_id=editor_user.id, lang_code=lang).first()
                if udd and udd.common_name:
                    user_descrs[dso_list_item.dso_id] = udd.common_name
                else:
                    user_descrs[dso_list_item.dso_id] = dso_list_item.deepskyObject.name

    theme = request.args.get('theme', '')
    inverted_accordion = theme in ['dark', 'night']

    return render_template('main/catalogue/dso_list_info.html', dso_list=dso_list, type='info', dso_list_descr=dso_list_descr, dso_list_items=dso_list_items,
                           user_descrs=user_descrs, season=season, search_form=search_form, inverted_accordion=inverted_accordion, observed=observed)


@main_dso_list.route('/dso-list/<string:dso_list_id>/chart', methods=['GET', 'POST'])
def dso_list_chart(dso_list_id):
    dso_list = _find_dso_list(dso_list_id)
    if dso_list is None:
        abort(404)

    form  = ChartForm()

    dso_id = request.args.get('dso_id')
    dso_list_item = None
    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        dso_list_item = next((x for x in dso_list.dso_list_items if x.deepskyObject.id == idso_id), None)

    if not dso_list_item:
        dso_list_item = DsoListItem.query.filter_by(dso_list_id=dso_list.id, item_id=1).first()

    lang, editor_user = get_lang_and_editor_user_from_request()
    dso_list_descr = DsoListDescription.query.filter_by(dso_list_id=dso_list.id, lang_code=lang).first()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = dso_list_item.deepskyObject.ra if dso_list_item else 0
            form.dec.data = dso_list_item.deepskyObject.dec if dso_list_item else 0

    if dso_list_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='dso_list', back_id=dso_list.id, dso_id=dso_list_item.deepskyObject.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    chart_control = common_prepare_chart_data(form)

    return render_template('main/catalogue/dso_list_info.html', fchart_form=form, type='chart', dso_list=dso_list, dso_list_descr=dso_list_descr,
                           chart_control=chart_control, default_chart_iframe_url=default_chart_iframe_url)


@main_dso_list.route('/dso-list/<string:dso_list_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def  dso_list_chart_pos_img(dso_list_id, ra, dec):
    highlights_dso_list = _find_highlights_dso_list(dso_list_id)
    if highlights_dso_list is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_dso_list.route('/dso-list/<string:dso_list_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def dso_list_chart_legend_img(dso_list_id, ra, dec):
    highlights_dso_list = _find_highlights_dso_list(dso_list_id)
    if highlights_dso_list is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_dso_list.route('/dso-list/<string:dso_list_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def dso_list_chart_pdf(dso_list_id, ra, dec):
    highlights_dso_list = _find_highlights_dso_list(dso_list_id)
    if highlights_dso_list is None:
        abort(404)

    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_dso_list=highlights_dso_list)

    return send_file(img_bytes, mimetype='application/pdf')


