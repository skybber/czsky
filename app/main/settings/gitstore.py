import os, re
import shutil

from pathlib import Path

from datetime import datetime

from flask import current_app
import git
from Crypto.PublicKey import RSA

from app import db

from app.models import Constellation, DeepskyObject, User, UserConsDescription, UserDsoDescription

PRIVATE_KEY_PATH = 'ssh/id_git'

def get_content_repository_path(user):
    return os.path.join(current_app.config.get('USER_DATA_DIR'), user.user_name, 'git-content-repository')

def get_ssh_key_dir_path(user):
    return os.path.join(current_app.config.get('USER_DATA_DIR'), user.user_name, 'ssh')

def get_ssh_private_key_path(user):
    return os.path.join(get_ssh_key_dir_path(user), 'id_git')

def _get_git_ssh_command(user_name, ssh_private_key, from_repo):
    path = Path(current_app.config.get('USER_DATA_DIR'), user_name, PRIVATE_KEY_PATH)
    if not path.exists():
        path.parent.mkdir(mode=0o711,parents=True, exist_ok=True)
    private_key = ssh_private_key
    if not private_key.endswith('\n'):
        private_key += '\n'
    with open(path, "w") as f:
        f.write(private_key)
    os.chmod(path, 0o600)
    return 'ssh -i ' + (('../' + PRIVATE_KEY_PATH) if from_repo else str(path))

def _finalize_git_ssh_command(owner):
    path = Path(current_app.config.get('USER_DATA_DIR'), owner.user_name, 'ssh/id_git')
    if path.exists():
        path.unlink()

def save_public_content_data_to_git(owner, commit_message):
    editor_user = User.get_editor_user()
    if not editor_user:
        raise EnvironmentError('User Editor not found.')
    repository_path = os.path.join(os.getcwd(), get_content_repository_path(owner))
    gitrepopath = os.path.join(repository_path, '.git')
    if not os.path.isdir(repository_path) or not os.path.isdir(gitrepopath):
        if not os.path.isdir(repository_path.join('.git')):
            print("HUH")
        if not os.path.isdir(repository_path):
            shutil.rmtree(repository_path)
        os.makedirs(repository_path, exist_ok=True)
        try:
            git.Repo.clone_from(owner.git_content_repository, repository_path,
                                env={'GIT_SSH_COMMAND': _get_git_ssh_command(owner.user_name, owner.git_content_ssh_private_key, False)})
        finally:
            _finalize_git_ssh_command(owner)

    files = []
    for d in UserDsoDescription.query.filter_by(user_id=editor_user.id):
        repo_file_name = os.path.join(d.lang_code,'dso', d.deepSkyObject.name + '.md')
        filename = os.path.join(repository_path, repo_file_name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('name: ' + str(d.common_name) + '\n')
            f.write('rating: ' + str(d.rating) + '\n')
            f.write('---\n')
            f.write(d.text)
        files.append(repo_file_name)

    for c in UserConsDescription.query.filter_by(user_id=editor_user.id):
        repo_file_name = os.path.join(c.lang_code, 'constellation', c.constellation.name + '.md')
        filename = os.path.join(repository_path, repo_file_name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('name: ' + str(c.common_name) + '\n')
            f.write('---\n')
            f.write(c.text)
        files.append(repo_file_name)

    repo = git.Repo(repository_path)
    try:
        with repo.git.custom_environment(GIT_SSH_COMMAND=_get_git_ssh_command(owner.user_name, owner.git_content_ssh_private_key, True)):
            repo.index.add(files)
            repo.index.commit(commit_message)
            repo.remotes.origin.push()
    finally:
        _finalize_git_ssh_command(owner)

def _read_line(f, expected=None, mandatory=False):
    line = f.readline()
    match = re.fullmatch(expected, line)
    return match

def load_public_content_data_from_git(owner):
    editor_user = User.get_editor_user()
    repository_path = os.path.join(os.getcwd(), get_content_repository_path(owner))

    repo = git.Repo(repository_path)
    try:
        with repo.git.custom_environment(GIT_SSH_COMMAND=_get_git_ssh_command(owner.user_name, owner.git_content_ssh_private_key, False)):
            repo.remotes.origin.pull()
    finally:
        _finalize_git_ssh_command(owner)

    for lang_code_dir in [f for f in os.listdir(repository_path) if os.path.isdir(os.path.join(repository_path, f)) and f not in  ['.git', 'images']]:
        dso_dir = os.path.join(repository_path, lang_code_dir, 'dso')
        files = [f for f in os.listdir(dso_dir) if os.path.isfile(os.path.join(dso_dir, f))]
        for dso_name_md in files:
            with open(os.path.join(dso_dir, dso_name_md), 'r') as f:
                if not dso_name_md.endswith('.md'):
                    continue
                dso_name = dso_name_md[:-3]
                _read_line(f, '---\n')
                mname = _read_line(f, r'name:\s*()\n')
                mrating = _read_line(f, r'rating:\s*()\n')
                common_name = mname.group(1) if mname else ''
                rating = mrating.group(1) if mrating else '5'
                _read_line(f, '---\n')
                text = f.read()
                dso_description = UserDsoDescription.query.filter_by(user_id=owner.id)\
                        .filter_by(lang_code=lang_code_dir) \
                        .join(UserDsoDescription.deepSkyObject, aliased=True) \
                        .filter_by(name=dso_name) \
                        .first()
                if not dso_description:
                    dso = DeepskyObject.query.filter_by(name=dso_name).first()
                    if not dso:
                        continue
                    dso_description = UserDsoDescription(
                        dso_id = dso.id,
                        user_id = editor_user.id,
                        lang_code = lang_code_dir,
                        cons_order = 1,
                        create_by = editor_user.id,
                        create_date = datetime.now(),
                    )
                dso_description.common_name = common_name
                dso_description.rating = int(rating)
                dso_description.text = text
                dso_description.update_by = editor_user.id
                dso_description.update_date = datetime.now()
                db.session.add(dso_description)

        constellation_dir = os.path.join(repository_path, lang_code_dir, 'constellation')
        files = [f for f in os.listdir(constellation_dir) if os.path.isfile(os.path.join(constellation_dir, f))]
        for constellation_name_md in files:
            with open(os.path.join(constellation_dir, constellation_name_md), 'r') as f:
                if not constellation_name_md.endswith('.md'):
                    continue
                constellation_name = constellation_name_md[:-3]
                _read_line(f, '---\n')
                mname = _read_line(f, r'name:\s*()\n')
                common_name = mname.group(1) if mname else ''
                _read_line(f, '---\n')
                text = f.read()
                cons_description = UserConsDescription.query.filter_by(user_id=owner.id)\
                        .filter_by(lang_code=lang_code_dir) \
                        .join(UserConsDescription.constellation, aliased=True) \
                        .filter_by(name=constellation_name) \
                        .first()
                if not cons_description:
                    constellation = Constellation.query.filter_by(name=constellation_name).first()
                    if not constellation:
                        continue
                    cons_description = UserConsDescription(
                        constellation_id = constellation.id,
                        user_id = editor_user.id,
                        lang_code = lang_code_dir,
                        create_by = editor_user.id,
                        create_date = datetime.now(),
                    )
                cons_description.common_name = common_name
                cons_description.text = text
                cons_description.update_by = editor_user.id
                cons_description.update_date = datetime.now()
                db.session.add(cons_description)

    db.session.commit()

def save_personal_data_to_git(owner, commit_message):
    pass

def load_personal_data_from_git(owner):
    pass
