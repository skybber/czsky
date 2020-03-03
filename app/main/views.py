from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.commons.dso_utils import normalize_dso_name
from app.models import Constellation, DeepskyObject, EditableHTML


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

@main.route('/search')
def global_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)
    constellation = Constellation.query.filter(Constellation.name.like('%' + query + '%')).first()
    if constellation:
        return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.iau_code))

    normalized_name = normalize_dso_name(query)
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    if dso:
        return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name))
