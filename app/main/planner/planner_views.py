import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.commons.dso_utils import normalize_dso_name

main_planner = Blueprint('main_planner', __name__)


@main_planner.route('/planner-menu', methods=['GET'])
@login_required
def planner_menu():
    return render_template('main/planner/planner_menu.html')
