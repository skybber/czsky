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
    user_descr = UserStarDescription.query.filter_by(id=star_id).first()
    if user_descr is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    if not from_constellation_id:
        from_constellation_id = user_descr.constellation_id
    from_observation_id = request.args.get('from_observation_id')

    editable=current_user.is_editor()
    return render_template('main/catalogue/star_info.html', type='info', user_descr=user_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id, editable=editable)

@main_star.route('/star/<int:star_id>/edit', methods=['GET', 'POST'])
@login_required
def star_edit(star_id):
    """Update user star description object."""
    user_descr = UserStarDescription.query.filter_by(id=star_id).first()
    if user_descr is None:
        abort(404)
    if not current_user.is_editor():
        abort(403)

    form = StarEditForm()
    if request.method == 'GET':
        form.common_name.data = user_descr.common_name
        form.text.data = user_descr.text
    elif form.validate_on_submit():
        user_descr.common_name = form.common_name.data
        user_descr.text = form.text.data
        user_descr.update_by = current_user.id
        user_descr.update_date = datetime.now()
        db.session.add(user_descr)
        db.session.commit()
        flash('Star description successfully updated', 'form-success')

    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')

    return render_template('main/catalogue/star_edit.html', form=form, user_descr=user_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           )
