import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_required,
    logout_user,
)

from app import db

from app.models import Permission, User

from app.main.settings.gitstore import get_ssh_public_key_path,create_new_ssh_key

from .usersettings_forms import (
    DeleteAccountForm,
    PasswordForm,
    PublicProfileForm,
    SSHKeyForm,
)

from .delete_account_utils import process_delete_account

main_usersettings = Blueprint('main_usersettings', __name__)

@main_usersettings.route('/user-settings/public-profile', methods=['GET', 'POST'])
@login_required
def public_profile():
    form = PublicProfileForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            current_user.full_name = form.full_name.data
            current_user.email = form.email.data
            db.session.add(current_user)
            db.session.commit()
            flash('Public profile successfully created', 'form-success')
    else:
        form.user_name.data = current_user.user_name
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email

    return render_template('main/usersettings/usersettings_edit.html', type='public_profile', form=form)

@main_usersettings.route('/user-settings/account', methods=['GET', 'POST'])
@login_required
def user_account():
    form1 = PasswordForm()
    form2 = DeleteAccountForm()
    return render_template('main/usersettings/usersettings_edit.html', type='user_account', form1=form1, form2=form2)

@main_usersettings.route('/user-settings/change_password', methods=['POST'])
@login_required
def change_password():
    form1 = PasswordForm()
    form2 = DeleteAccountForm()
    if form1.validate_on_submit():
        if current_user.verify_password(form1.current_password.data):
            current_user.password = form1.new_password.data
            db.session.add(current_user)
            db.session.commit()
            flash('Your password has been updated.', 'form-success')
        else:
            flash('Original password is invalid.', 'form-error')
    return render_template('main/usersettings/usersettings_edit.html', type='user_account', subtype='change_password', form1=form1, form2=form2)

@main_usersettings.route('/user-settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    form1 = PasswordForm()
    form2 = DeleteAccountForm()
    if form2.validate_on_submit():
        if current_user.verify_password(form2.password.data):
            process_delete_account(current_user)
            logout_user()
            flash('Your account was deleted.', 'form-success')
            return redirect(url_for('main.index'))
        else:
            flash('Original password is invalid.', 'form-error')
    return render_template('main/usersettings/usersettings_edit.html', type='user_account', subtype='delete_account', form1=form1, form2=form2)


@main_usersettings.route('/user-settings/git-repository', methods=['GET', 'POST'])
@login_required
def git_repository():
    return render_template('main/usersettings/usersettings_edit.html', type='git_repository')

@main_usersettings.route('/user-settings/ssh-key-info', methods=['GET'])
@login_required
def ssh_key_info():
    """Show ssh public key."""
    form = SSHKeyForm()
    public_key_path = get_ssh_public_key_path(current_user)
    form.ssh_public_key.data = 'None'
    if os.path.isfile(public_key_path):
        with open(public_key_path, 'r') as f:
            form.ssh_public_key.data = f.read()

    return render_template('account/manage.html', form=form, ssh_key_info=True)

@main_usersettings.route('/user-settings/ssh-key-create', methods=['GET'])
@login_required
def ssh_key_create():
    create_new_ssh_key(current_user)
    flash('New ssh key was created.', 'form-success')
    return redirect(url_for('account.ssh_key_info'))
