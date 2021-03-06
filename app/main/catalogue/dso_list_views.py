from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from posix import wait

from app.models import Constellation, DsoList, DsoListDescription, User, UserDsoDescription
from app.commons.search_utils import process_session_search
from app.commons.utils import get_lang_and_editor_user_from_request

from .dso_list_forms import (
    SearchDsoListForm,
)

main_dso_list = Blueprint('main_dso_list', __name__)

def _find_dso_list(dso_list_id):
    try:
        int_id = int(dso_list_id)
        return DsoList.query.filter_by(id=int_id).first()
    except ValueError:
        return DsoList.query.filter_by(name=dso_list_id).first()

@main_dso_list.route('/dso-lists-menu', methods=['GET'])
def dso_lists_menu():
    dso_lists = DsoList.query.all()
    lang, editor_user = get_lang_and_editor_user_from_request()
    return render_template('main/catalogue/dso_list_menu.html', dso_lists=dso_lists, lang_code=lang)

@main_dso_list.route('/dso-list/<string:dso_list_id>', methods=['GET','POST'])
@main_dso_list.route('/dso-list/<string:dso_list_id>/info', methods=['GET','POST'])
def dso_list_info(dso_list_id):
    """View a dso list info."""
    dso_list = _find_dso_list(dso_list_id)
    if dso_list is None:
        abort(404)

    search_form = SearchDsoListForm()

    if not process_session_search([('dso_list_season', search_form.season),]):
        return redirect(url_for('main_dso_list.dso_list_info', dso_list_id=dso_list_id))

    lang, editor_user = get_lang_and_editor_user_from_request()

    if search_form.season.data and search_form.season.data != 'All':
        constell_ids = set()
        for constell_id in db.session.query(Constellation.id).filter(Constellation.season==search_form.season.data):
            constell_ids.add(constell_id[0])
    else:
        constell_ids = None

    dso_list_descr = DsoListDescription.query.filter_by(dso_list_id=dso_list.id, lang_code=lang).first()

    dso_list_items = []
    user_descrs = {} if dso_list.show_descr_name else None
    for dso_list_item in dso_list.dso_list_items:
        if constell_ids is None or dso_list_item.deepskyObject.constellation_id in constell_ids:
            dso_list_items.append(dso_list_item)
            if not user_descrs is None:
                udd =   UserDsoDescription.query.filter_by(dso_id=dso_list_item.dso_id, user_id=editor_user.id, lang_code=lang).first()
                if udd and udd.common_name:
                    user_descrs[dso_list_item.dso_id] = udd.common_name
                else:
                    user_descrs[dso_list_item.dso_id] = dso_list_item.deepskyObject.name

    season = search_form.season.data if search_form.season.data and search_form.season.data!='All' else None

    return render_template('main/catalogue/dso_list_info.html', dso_list=dso_list, dso_list_descr=dso_list_descr, dso_list_items=dso_list_items,
                           user_descrs=user_descrs, season=season, search_form=search_form)


