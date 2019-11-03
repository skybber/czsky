from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Permission, UserStarDescription
from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search

main_star = Blueprint('main_star', __name__)

from .star_forms import (
    StarEditForm,
)

@main_star.route('/star/<int:star_id>')
@main_star.route('/star/<int:star_id>/info')
def star_info(star_id):
    """View a star info."""
    star_descr = UserStarDescription.query.filter_by(id=star_id).first()
    if star_descr is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    editable=current_user.can(Permission.EDIT_COMMON_CONTENT)
    return render_template('main/star/star_info.html', type='info', start_descr=star_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id, editable=editable)

@main_star.route('/star/<int:star_id>/edit', methods=['GET', 'POST'])
@login_required
def star_edit(dso_id):
    """Update user star description object."""
    star_descr = UserStarDescription.query.filter_by(id=star_id).first()
    if star_descr is None:
        abort(404)
    if not current_user.can(Permission.EDIT_COMMON_CONTENT):
        abort(403)

    form = StarEditForm()
    if request.method == 'GET':
        form.common_name.data = star_descr.common_name
        form.text.data = star_descr.text
    elif form.validate_on_submit():
        star_descr.common_name = form.common_name.data
        star_descr.text = form.text.data
        star_descr.update_by = current_user.id
        star_descr.update_date = datetime.now()
        db.session.add(star_descr)
        db.session.commit()
        flash('Star description successfully updated', 'form-success')

    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')

    return render_template('main/catalogue/star_edit.html', form=form, star_descr=star_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           )
