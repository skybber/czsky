from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
)
from flask_login import current_user, login_required

from app.models import EditableHTML

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

@main.route('/swtheme')
def switch_theme():
    session['themlight'] = not session.get('themlight', False)
    return redirect(request.referrer)
