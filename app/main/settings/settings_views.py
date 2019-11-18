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
from app.decorators import editor_required
from .gitstore import save_content_data_to_git, load_content_data_from_git, save_personal_data_to_git, load_personal_data_from_git
from .settings_forms import GitSaveForm
from posix import wait

main_settings = Blueprint('main_settings', __name__)

ITEMS_PER_PAGE = 10

@main_settings.route('/settings', methods=['GET'])
@login_required
def settings():
    return render_template('main/settings/settings.html')

@main_settings.route('/data-store-personal', methods=['GET'])
@login_required
def data_store_personal():
    return _render_data_store(current_user.git_repository, 'repo_personal')

@main_settings.route('/data-store-content', methods=['GET'])
@login_required
@editor_required
def data_store_content():
    return _render_data_store(current_user.git_content_repository, 'repo_content')

def _render_data_store(git_repository, subtype):
    save_form = GitSaveForm()
    git_enabled = _is_git_enabled(subtype)
    git_save = request.args.get('git_save', None)
    git_load = request.args.get('git_load', None)

    return render_template('main/settings/data_store.html',
                                save_form=save_form,
                                git_enabled=git_enabled,
                                git_url=git_repository,
                                git_save=git_save,
                                git_load=git_load,
                                subtype=subtype,)

@main_settings.route('/git-save', methods=['POST'])
@login_required
def git_save():
    form = GitSaveForm()
    if form.validate_on_submit():
        subtype = request.args.get('subtype', None)
        if _is_git_enabled(subtype):
            if subtype == 'repo_personal':
                try:
                    save_personal_data_to_git(current_user, form.commit_message.data)
                    flash('User data was stored to git repository.', 'form-success')
                except git.GitCommandError as e:
                    flash('Storing data to Git repository failed.', 'form-error')
            else:
                try:
                    save_content_data_to_git(current_user, form.commit_message.data)
                    flash('Content data was stored to git repository.', 'form-success')
                except git.GitCommandError as e:
                    flash('Storing content data to Git repository failed.', 'form-success')
    return redirect(url_for('main_settings.data_store', git_save='1'))

@main_settings.route('/git-load', methods=['POST'])
@login_required
def git_load():
    subtype = request.args.get('subtype', None)
    if _is_git_enabled(subtype):
        if subtype == 'repo_personal':
            try:
                load_personal_data_from_git(current_user)
                flash('User data loaded from Git repository.', 'form-success')
            except git.GitCommandError as e:
                flash('Loading data from Git repository failed.', 'form-success')
        else:
            editor_user = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
            try:
                load_content_data_from_git(current_user, editor_user)
                flash('Content data loaded from Git repository.', 'form-success')
            except git.GitCommandError as e:
                flash('Loading content data from Git repository failed.', 'form-success')
    return redirect(url_for('main_settings.data_store', git_load='1'))

def _is_git_enabled(subtype):
    if subtype == 'repo_content':
        return _is_git_content_enabled();
    if subtype == 'repo_personal':
        return _is_git_personal_enabled();
    return False

def _is_git_personal_enabled():
    return current_user.git_repository and \
             current_user.git_ssh_public_key and \
             current_user.git_ssh_private_key

def _is_git_content_enabled():
    if not current_user.is_editor():
        return False
    return current_user.git_content_repository and \
             current_user.git_content_ssh_public_key and \
             current_user.git_content_ssh_private_key
