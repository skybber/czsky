import threading
from posix import wait

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
from .gitstore import save_public_content_data_to_git, load_public_content_data_from_git, save_personal_data_to_git, load_personal_data_from_git
from .userdata_forms import GitSaveForm

main_userdata = Blueprint('main_userdata', __name__)

ITEMS_PER_PAGE = 10

@main_userdata.route('/userdata-menu', methods=['GET'])
@login_required
def userdata_menu():
    return render_template('main/userdata/userdata_menu.html')

@main_userdata.route('/data-store-personal', methods=['GET'])
@login_required
def data_store_personal():
    return _render_data_store(current_user.git_repository, 'repo_personal')

@main_userdata.route('/data-store-content', methods=['GET'])
@login_required
@editor_required
def data_store_content():
    return _render_data_store(current_user.git_content_repository, 'repo_content')

def _render_data_store(git_repository, subtype):
    save_form = GitSaveForm()
    git_enabled = _is_git_enabled(subtype)
    git_save = request.args.get('git_save', None)
    git_load = request.args.get('git_load', None)

    return render_template('main/userdata/data_store.html',
                                save_form=save_form,
                                git_enabled=git_enabled,
                                git_url=git_repository,
                                git_save=git_save,
                                git_load=git_load,
                                subtype=subtype,)

@main_userdata.route('/git-save', methods=['POST'])
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
                    flash('Storing data to Git repository failed.' + str(e), 'form-error')
            else:
                try:
                    save_public_content_data_to_git(current_user, form.commit_message.data)
                    flash('Content data was stored to git repository.', 'form-success')
                except git.GitCommandError as e:
                    flash('Storing content data to Git repository failed.' + str(e), 'form-error')
    return redirect(url_for('main_userdata.data_store_content', git_save='1'))

@main_userdata.route('/git-load', methods=['GET'])
@login_required
def git_load():
    subtype = request.args.get('subtype', None)
    if _is_git_enabled(subtype):
        if subtype == 'repo_personal':
            try:
                load_personal_data_from_git(current_user)
                flash('User data loaded from Git repository.', 'form-success')
            except git.GitCommandError as e:
                flash('Loading data from Git repository failed.' + str(e), 'form-success')
        else:
            try:
                thread = threading.Thread(target=_do_load_public_content_data_from_git, args=(current_app._get_current_object(), current_user.user_name, ))
                thread.start()
                flash('Content data is loading from Git repository...', 'form-success')
            except git.GitCommandError as e:
                flash('Loading content data from Git repository failed.' + str(e), 'form-success')
    return redirect(url_for('main_userdata.data_store_content', git_load='1'))

def _do_load_public_content_data_from_git(app, user_name):
    with app.app_context():
        load_public_content_data_from_git(user_name)

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
