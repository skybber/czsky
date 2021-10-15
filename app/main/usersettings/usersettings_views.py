from Crypto.PublicKey import RSA

from flask import (
    Blueprint,
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

from .usersettings_forms import (
    DeleteAccountForm,
    PasswordForm,
    PublicProfileForm,
    GitContentSSHKeyForm,
    GitSSHKeyForm,
)

from .delete_account_utils import process_delete_account
from app.commons.countries import countries

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

    return render_template('main/usersettings/usersettings_edit.html', type='public_profile', form=form, countries=countries)


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


@main_usersettings.route('/user-settings/git-repository', methods=['GET'])
@login_required
def git_repository():
    """Show ssh public key."""
    form1 = GitSSHKeyForm()
    form1.git_repository.data = current_user.git_repository
    form1.ssh_public_key.data = current_user.git_ssh_public_key

    form2 = None
    if current_user.is_editor():
        form2 = GitContentSSHKeyForm()
        form2.git_repository.data = current_user.git_content_repository
        form2.ssh_public_key.data = current_user.git_content_ssh_public_key
    return render_template('main/usersettings/usersettings_edit.html', form1=form1, form2=form2, type='git_repository')


@main_usersettings.route('/user-settings/git-personal-repository', methods=['POST'])
@login_required
def git_personal_repository():
    """Post personal git repository settings."""
    form1 = GitSSHKeyForm()
    form2 = None
    if current_user.is_editor():
        form2 = GitContentSSHKeyForm()
        form2.git_repository.data = current_user.git_content_repository
        form2.ssh_public_key.data = current_user.git_content_ssh_public_key
    if form1.validate_on_submit():
        current_user.git_repository = form1.git_repository.data
        db.session.add(current_user)
        db.session.commit()
        flash('Repository settings has been updated.', 'form-success')
    return render_template('main/usersettings/usersettings_edit.html', form1=form1, form2=form2, type='git_repository', subtype='personal_repo_key')


@main_usersettings.route('/user-settings/git-content-repository', methods=['POST'])
@login_required
def git_content_repository():
    """Post personal git repository settings."""
    form1 = GitSSHKeyForm()
    form1.git_repository.data = current_user.git_repository
    form1.ssh_public_key.data = current_user.git_ssh_public_key
    form2 = None
    if current_user.is_editor():
        form2 = GitContentSSHKeyForm()
        if form2.validate_on_submit():
            current_user.git_content_repository = form2.git_repository.data
            db.session.add(current_user)
            db.session.commit()
            flash('Content repository settings has been updated.', 'form-success')
    return render_template('main/usersettings/usersettings_edit.html', form1=form1, form2=form2, type='git_repository', subtype='content_repo_key')


@main_usersettings.route('/user-settings/git-ssh-key-create', methods=['GET'])
@login_required
def git_ssh_key_create():
    key = RSA.generate(2048)
    current_user.git_ssh_private_key = key.export_key().decode("ascii")
    current_user.git_ssh_public_key = key.publickey().export_key('OpenSSH').decode("ascii")
    db.session.add(current_user)
    db.session.commit()
    flash('New ssh key was created.', 'form-success')
    return redirect(url_for('main_usersettings.git_repository'))


@main_usersettings.route('/user-settings/git-content-ssh-key-create', methods=['GET'])
@login_required
def git_content_ssh_key_create():
    key = RSA.generate(2048)
    current_user.git_content_ssh_private_key = key.export_key().decode("ascii")
    current_user.git_content_ssh_public_key = key.publickey().export_key('OpenSSH').decode("ascii")
    db.session.add(current_user)
    db.session.commit()
    flash('New content ssh key was created.', 'form-success')
    return redirect(url_for('main_usersettings.git_repository'))


@main_usersettings.route('/user-settings/git-ssh-key-delete', methods=['GET'])
@login_required
def git_ssh_key_delete():
    current_user.git_ssh_private_key = None
    current_user.git_ssh_public_key = None
    db.session.add(current_user)
    db.session.commit()
    flash('SSH key was deleted.', 'form-success')
    return redirect(url_for('main_usersettings.git_repository'))


@main_usersettings.route('/user-settings/git-content-ssh-key-delete', methods=['GET'])
@login_required
def git_content_ssh_key_delete():
    current_user.git_content_ssh_private_key = None
    current_user.git_content_ssh_public_key = None
    db.session.add(current_user)
    db.session.commit()
    flash('SSH key for content was deleted.', 'form-success')
    return redirect(url_for('main_usersettings.git_repository'))


