import re
import math

from flask import (
    abort,
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

from sqlalchemy import func

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

    query = query.strip()

    r_radec = re.compile(r'''(\d\d?)[h:]?[ ]?(\d\d?)[m:]?[ ]?(\d\d?(\.\d\d?\d?)?)[s:]?[ ]?([+-]?\d\d)?[:°]?[ ]?(\d\d?)[:′']?[ ]?(\d\d?(\.\d\d?\d?)?)[″"]?''')
    m = r_radec.match(query)
    if m is not None:
        ra = math.pi * (int(m.group(1))/12 + int(m.group(2))/(12*60) + float(m.group(3))/(12*60*60))
        dec_base = int(m.group(5))/180
        if dec_base > 0:
            multipl = 1.0
        elif dec_base < 0:
            multipl = -1.0
        else:
            multipl = 0.0
        dec = math.pi * (dec_base + multipl * int(m.group(6))/(180*60) + multipl * float(m.group(7))/(180*60*60))
        return redirect(url_for('main_chart.chart', ra=ra, dec=dec))

    constellation = Constellation.query.filter(Constellation.name.like('%' + query + '%')).first() or \
                    Constellation.query.filter(func.lower(Constellation.iau_code) == func.lower(query)).first()

    if constellation:
        return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.iau_code))

    if query and query.isdigit():
        query = 'NGC' + query

    normalized_name = normalize_dso_name(query)
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    if dso:
        return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name))

    abort(404)
