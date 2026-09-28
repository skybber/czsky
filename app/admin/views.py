from datetime import date
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_user,
    login_required
)
from flask_babel import gettext
from sqlalchemy.exc import IntegrityError

from app.compat.flask_rq import get_queue

from app.commons.utils import is_safe_url
from app.commons.comet_utils import COMET_ORBIT_FIELDS, refresh_manual_comet
from app.admin.comet_forms import DeleteManualCometForm, ManualCometForm

from app import db, get_locale
from app.admin.forms import (
    DisableUserForm,
    ChangeAccountTypeForm,
    ChangeUserEmailForm,
    InviteUserForm,
    NewUserForm,
)
from app.decorators import admin_required
from app.email import send_email
from app.models import (
    Comet, CometObservation, EditableHTML, Observation, ObservedListItem,
    Role, SessionPlanItem, User, UserObjectListItem,
)

admin = Blueprint('admin', __name__)


@admin.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard page."""
    return render_template('admin/index.html')


@admin.route('/comets')
@login_required
@admin_required
def comets():
    comets = Comet.query.filter_by(is_manual=True).order_by(Comet.designation).all()
    return render_template('admin/comets.html', comets=comets)


@admin.route('/comets/new', methods=['GET', 'POST'])
@admin.route('/comets/<int:comet_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_comet(comet_id=None):
    comet = None
    if comet_id is not None:
        comet = Comet.query.filter_by(id=comet_id, is_manual=True).first_or_404()
    form = ManualCometForm(obj=comet)
    if request.method == 'GET' and comet:
        form.epoch.data = date(
            int(comet.perturbed_epoch_year), int(comet.perturbed_epoch_month),
            int(comet.perturbed_epoch_day),
        )
    if form.validate_on_submit():
        if comet is None:
            comet = Comet(comet_id='manual-' + uuid4().hex, is_manual=True, is_disintegrated=False)
        for field in COMET_ORBIT_FIELDS + ('designation', 'magnitude_g', 'magnitude_k', 'reference'):
            setattr(comet, field, getattr(form, field).data)
        comet.perturbed_epoch_year = form.epoch.data.year
        comet.perturbed_epoch_month = form.epoch.data.month
        comet.perturbed_epoch_day = form.epoch.data.day
        try:
            refresh_manual_comet(comet)
        except (ValueError, ArithmeticError, OSError):
            db.session.rollback()
            current_app.logger.exception('Could not calculate manually entered comet orbit')
            flash('Could not calculate the orbit. Check the elements and availability of the ephemeris.', 'form-error')
        else:
            db.session.add(comet)
            db.session.commit()
            flash('Comet saved. It is publicly visible.', 'form-success')
            return redirect(url_for('admin.comets'))
    return render_template('admin/edit_comet.html', form=form, comet=comet)


@admin.route('/comets/<int:comet_id>/delete', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_comet(comet_id):
    query = Comet.query.filter_by(id=comet_id, is_manual=True)
    if request.method == 'POST':
        query = query.with_for_update()
    comet = query.first_or_404()
    form = DeleteManualCometForm()
    references = [
        label for model, label in (
            (Observation, gettext('Observations')),
            (CometObservation, gettext('COBS observations')),
            (SessionPlanItem, gettext('Session plans')),
            (ObservedListItem, gettext('Observed lists')),
            (UserObjectListItem, gettext('User object lists')),
        ) if model.query.filter_by(comet_id=comet.id).first() is not None
    ]
    if form.validate_on_submit():
        if references:
            flash(gettext('This comet cannot be deleted because it has linked records.'), 'form-error')
        else:
            try:
                db.session.delete(comet)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(gettext('The comet could not be deleted because it is still referenced. '
                              'Reload this page to see its linked records.'), 'form-error')
            else:
                flash(gettext('Comet deleted.'), 'form-success')
                return redirect(url_for('admin.comets'))
    return render_template('admin/delete_comet.html', comet=comet, form=form,
                           references=references)


@admin.route('/new-user', methods=['GET', 'POST'])
@login_required
@admin_required
def new_user():
    """Create a new user."""
    form = NewUserForm()
    if form.validate_on_submit():
        user = User(
            role=form.role.data,
            user_name=form.user_name.data,
            full_name=form.full_name.data,
            email=form.email.data,
            password=form.password.data,
            confirmed=True
            )
        db.session.add(user)
        db.session.commit()
        flash('User {} successfully created'.format(user.full_name),
              'form-success')
    return render_template('admin/new_user.html', form=form)


@admin.route('/invite-user', methods=['GET', 'POST'])
@login_required
@admin_required
def invite_user():
    """Invites a new user to create an account and set their own password."""
    form = InviteUserForm()
    if form.validate_on_submit():
        user = User(
            role=form.role.data,
            user_name=form.user_name.data,
            full_name=form.full_name.data,
            email=form.email.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        invite_link = url_for(
            'account.join_from_invite',
            user_id=user.id,
            token=token,
            _external=True)
        get_queue().enqueue(
            send_email,
            recipient=user.email,
            subject='You Are Invited To Join',
            template='account/email/invite',
            locale = get_locale(),
            user=user,
            invite_link=invite_link,
        )
        flash('User {} successfully invited'.format(user.full_name),
              'form-success')
    return render_template('admin/new_user.html', form=form)


@admin.route('/users')
@login_required
@admin_required
def registered_users():
    """View all registered users."""
    users = User.query.all()
    roles = Role.query.all()
    return render_template(
        'admin/registered_users.html', users=users, roles=roles)


@admin.route('/user/<int:user_id>')
@admin.route('/user/<int:user_id>/info')
@login_required
@admin_required
def user_info(user_id):
    """View a user's profile."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    return render_template('admin/manage_user.html', user=user)


@admin.route('/user/<int:user_id>/change-email', methods=['GET', 'POST'])
@login_required
@admin_required
def change_user_email(user_id):
    """Change a user's email."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    form = ChangeUserEmailForm()
    if form.validate_on_submit():
        user.email = form.email.data
        db.session.add(user)
        db.session.commit()
        flash('Email for user {} successfully changed to {}.'.format(
            user.full_name, user.email), 'form-success')
    return render_template('admin/manage_user.html', user=user, form=form)


@admin.route(
    '/user/<int:user_id>/change-account-type', methods=['GET', 'POST'])
@login_required
@admin_required
def change_account_type(user_id):
    """Change a user's account type."""
    if current_user.id == user_id:
        flash('You cannot change the type of your own account. Please ask '
              'another administrator to do this.', 'error')
        return redirect(url_for('admin.user_info', user_id=user_id))

    user = User.query.get(user_id)
    if user is None:
        abort(404)
    form = ChangeAccountTypeForm()
    if request.method == 'GET':
        form.role.data = user.role
    elif form.validate_on_submit():
        user.role = form.role.data
        db.session.add(user)
        db.session.commit()
        flash('Role for user {} successfully changed to {}.'.format(
            user.full_name, user.role.name), 'form-success')

    return render_template('admin/manage_user.html', user=user, form=form)


@admin.route(
    '/user/<int:user_id>/disable-user', methods=['GET', 'POST'])
@login_required
@admin_required
def disable_user(user_id):
    """Disable user"""
    if current_user.id == user_id:
        flash('You cannot disable your own account. Please ask '
              'another administrator to do this.', 'error')
        return redirect(url_for('admin.user_info', user_id=user_id))

    user = User.query.get(user_id)
    if user is None:
        abort(404)
    form = DisableUserForm()
    if request.method == 'GET':
        form.is_disabled.data = user.is_disabled
    elif form.validate_on_submit():
        user.is_disabled = form.is_disabled.data
        db.session.add(user)
        db.session.commit()
        if user.is_disabled:
            flash('User {} was disabled.'.format(user.full_name), 'form-success')
        else:
            flash('User {} was enabled.'.format(user.full_name), 'form-success')

    return render_template('admin/manage_user.html', user=user, form=form)


@admin.route('/user/<int:user_id>/delete')
@login_required
@admin_required
def delete_user_request(user_id):
    """Request deletion of a user's account."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    return render_template('admin/manage_user.html', user=user)


@admin.route('/user/<int:user_id>/_delete')
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user's account."""
    if current_user.id == user_id:
        flash('You cannot delete your own account. Please ask another '
              'administrator to do this.', 'error')
    else:
        user = User.query.filter_by(id=user_id).first()
        db.session.delete(user)
        db.session.commit()
        flash('Successfully deleted user %s.' % user.full_name, 'success')
    return redirect(url_for('admin.registered_users'))


@admin.route('/_update_editor_contents', methods=['POST'])
@login_required
@admin_required
def update_editor_contents():
    """Update the contents of an editor."""

    edit_data = request.form.get('edit_data')
    editor_name = request.form.get('editor_name')

    editor_contents = EditableHTML.query.filter_by(
        editor_name=editor_name).first()
    if editor_contents is None:
        editor_contents = EditableHTML(editor_name=editor_name)
    editor_contents.value = edit_data

    db.session.add(editor_contents)
    db.session.commit()

    return 'OK', 200


@admin.route('/user/<int:user_id>/login_as_start', methods=['GET'])
@login_required
@admin_required
def login_as_start(user_id):
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    return render_template('admin/manage_user.html', user=user)


@admin.route('/user/<int:user_id>/login_as', methods=['GET'])
@login_required
@admin_required
def login_as(user_id):
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    login_user(user, False)
    flash('You are now logged in as ' + user.user_name + '.', 'success')
    next_url = request.args.get('next')
    if not is_safe_url(next_url):
        next_url = url_for('main.index')
    return redirect(next_url)
