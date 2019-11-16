from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

import git

from app.models import Permission, User
from .gitstore import save_user_data_to_git, load_user_data_from_git

main_settings = Blueprint('main_settings', __name__)

ITEMS_PER_PAGE = 10

@main_settings.route('/settings', methods=['GET'])
@login_required
def settings():
    return render_template('main/settings/settings.html')

@main_settings.route('/data-store', methods=['GET', 'POST'])
@login_required
def data_store():
    if current_user.can(Permission.EDIT_COMMON_CONTENT):
        user = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    else:
        user = current_user

    git_enabled = user.git_repository and \
                    user.git_ssh_public_key and \
                    user.git_ssh_private_key

    git_stored = False
    git_restored = False

    if git_enabled and request.method == 'POST':
        if request.form['submit'] == 'store':
            try:
                save_user_data_to_git(user)
                flash('User data stored to git repository.', 'form-success')
                git_stored = True
            except git.GitCommandError as e:
                flash('User data stored to git repository.', 'form-success')
                return
        elif request.form['submit'] == 'restore':
            load_user_data_from_git(user, current_user)
            flash('User data reloaded from git repository.', 'form-success')
            git_restored = True
    return render_template('main/settings/data_store.html',
                                git_enabled=git_enabled,
                                git_url=user.git_repository,
                                git_restored=git_restored,
                                git_stored=git_stored)
