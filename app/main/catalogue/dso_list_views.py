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

from app.models import DsoList, DsoListDescription, User

main_dso_list = Blueprint('main_dso_list', __name__)

@main_dso_list.route('/dso-lists-menu', methods=['GET'])
def dso_lists_menu():
    dso_lists = DsoList.query.all()
    return render_template('main/catalogue/dso_list_menu.html', dso_lists=dso_lists, lang_code='cs')

@main_dso_list.route('/dso-list/<int:dso_list_id>', methods=['GET'])
@main_dso_list.route('/dso-list/<int:dso_list_id>/info', methods=['GET'])
def dso_list_info(dso_list_id):
    """View a dso list info."""
    dso_list = DsoList.query.filter_by(id=dso_list_id).first()
    if dso_list is None:
        abort(404)
    dso_list_descr = DsoListDescription.query.filter_by(dso_list_id=dso_list.id, lang_code='cs').first()
    return render_template('main/catalogue/dso_list_info.html', dso_list=dso_list, dso_list_descr=dso_list_descr)

