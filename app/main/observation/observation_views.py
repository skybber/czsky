from flask import (
    Blueprint,
    render_template,
)
from flask_login import current_user, login_required


main_observation = Blueprint('main_observation', __name__)


@main_observation.route('/observation-menu', methods=['GET'])
@login_required
def observation_menu():
    return render_template('main/observation/observation_menu.html')

