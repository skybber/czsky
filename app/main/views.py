from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import EditableHTML
from app.commons.pagination import Pagination, get_page_parameter, get_page_args

main = Blueprint('main', __name__)

ITEMS_PER_PAGE = 10

@main.route('/')
def index():
    return render_template('main/index.html', is_anonymous=current_user.is_anonymous)


@main.route('/about')
def about():
    editable_html_obj = EditableHTML.get_editable_html('about')
    return render_template(
        'main/about.html', editable_html_obj=editable_html_obj)

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    return render_template('main/settings.html')

@main.route('/skyquality', methods=['GET', 'POST'])
@login_required
def skyquality():
    return render_template('main/skyquality/skyquality.html')

