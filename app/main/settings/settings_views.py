from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

import git

from app.models import Permission, User
from .gitstore import save_user_data_to_git, load_user_data_from_git
from .settings_forms import GitSaveForm
from posix import wait

main_settings = Blueprint('main_settings', __name__)

ITEMS_PER_PAGE = 10

@main_settings.route('/settings', methods=['GET'])
@login_required
def settings():
    return render_template('main/settings/settings.html')

@main_settings.route('/data-store', methods=['GET', 'POST'])
@login_required
def data_store():
    save_form = GitSaveForm()
    if current_user.can(Permission.EDIT_COMMON_CONTENT):
        user = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    else:
        user = current_user

    git_enabled = _is_git_enabled(user)

    git_save = request.args.get('git_save', None)
    git_load = request.args.get('git_load', None)

    return render_template('main/settings/data_store.html',
                                save_form=save_form,
                                git_enabled=git_enabled,
                                git_url=user.git_repository,
                                git_save=git_save,
                                git_load=git_load)

@main_settings.route('/git-save', methods=['POST'])
@login_required
def git_save():
    form = GitSaveForm()
    if form.validate_on_submit():
        if current_user.can(Permission.EDIT_COMMON_CONTENT):
            user = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
        else:
            user = current_user
        if _is_git_enabled(user):
            try:
                save_user_data_to_git(user, form.commit_message.data)
                flash('User data stored to git repository.', 'form-success')
            except git.GitCommandError as e:
                flash('User data stored to git repository.', 'form-success')
    return redirect(url_for('main_settings.data_store', git_save='1'))

@main_settings.route('/git-load', methods=['POST'])
@login_required
def git_load():
    if current_user.can(Permission.EDIT_COMMON_CONTENT):
        user = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    else:
        user = current_user
    if _is_git_enabled(user):
        load_user_data_from_git(user, current_user)
        flash('User data reloaded from git repository.', 'form-success')
    return redirect(url_for('main_settings.data_store', git_load='1'))

def _is_git_enabled(user):
    return user.git_repository and \
             user.git_ssh_public_key and \
             user.git_ssh_private_key
