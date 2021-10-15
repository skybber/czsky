from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

main_solarsystem = Blueprint('main_solarsystem', __name__)


@main_solarsystem.route('/solarsystem-menu', methods=['GET'])
def solarsystem_menu():
    return render_template('main/solarsystem/solarsystem_menu.html')
