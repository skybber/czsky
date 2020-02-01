import os, re
import shutil
import glob

from pathlib import Path

from datetime import datetime

from flask import current_app
import git
from Crypto.PublicKey import RSA

from app import db

from app.models import Constellation, DeepskyObject, User, UserConsDescription, UserDsoDescription, UserDsoApertureDescription

from app.commons.dso_utils import destructuralize_dso_name

PRIVATE_KEY_PATH = 'ssh/id_git'

def get_content_repository_path(user):
    return os.path.join(current_app.config.get('USER_DATA_DIR'), user.user_name, 'git-content-repository')

def get_ssh_key_dir_path(user):
    return os.path.join(current_app.config.get('USER_DATA_DIR'), user.user_name, 'ssh')

def get_ssh_private_key_path(user):
    return os.path.join(get_ssh_key_dir_path(user), 'id_git')

def _get_git_ssh_command(user_name, ssh_private_key, from_repo):
    path = Path(os.getcwd(), current_app.config.get('USER_DATA_DIR'), user_name, PRIVATE_KEY_PATH)
    if not path.exists():
        path.parent.mkdir(mode=0o711,parents=True, exist_ok=True)
    private_key = ssh_private_key
    if not private_key.endswith('\n'):
        private_key += '\n'
    with open(path, "w") as f:
        f.write(private_key)
    os.chmod(path, 0o400)
    return 'ssh -i ' + (('../' + PRIVATE_KEY_PATH) if from_repo else str(path))

def _finalize_git_ssh_command(user_name):
    path = Path(current_app.config.get('USER_DATA_DIR'), user_name, 'ssh/id_git')
    if path.exists():
        path.unlink()

def _actualize_repository(user_name, git_repository, git_ssh_private_key, repository_path):
    git_repopath = os.path.join(repository_path, '.git')
    if not os.path.isdir(repository_path) or not os.path.isdir(git_repopath):
        if os.path.isdir(repository_path):
            shutil.rmtree(repository_path) # remove repository_path in case there is no .git file
        os.makedirs(repository_path, exist_ok=True)
        try:
            git.Repo.clone_from(git_repository, repository_path,
                                env={'GIT_SSH_COMMAND': _get_git_ssh_command(user_name, git_ssh_private_key, False)})
        finally:
            _finalize_git_ssh_command(user_name)
    else:
        repo = git.Repo(repository_path)
        try:
            with repo.git.custom_environment(GIT_SSH_COMMAND=_get_git_ssh_command(user_name, git_ssh_private_key, True)):
                repo.remotes.origin.pull()
        finally:
            _finalize_git_ssh_command(user_name)

def _id_to_range(dso_id, range):
    nth_range = int(dso_id / range)
    return str(nth_range * range) + '-' + str((nth_range+1) * range)


def _get_dso_dir(cat_name, dso_id):
        if cat_name.startswith('PK'):
            return 'PK'
        if cat_name.startswith('NGC') or cat_name.startswith('IC'):
            return os.path.join('NGC', _id_to_range(dso_id, 100))
        return cat_name

def _get_user_name(user_id, user_name_cache):
    if user_id is None:
        return ''
    user_name = user_name_cache.get(user_id, None)
    if not user_name:
        user_name = User.query.filter_by(id=user_id).first().user_name
        user_name_cache[user_id] = user_name
    return user_name

def save_public_content_data_to_git(owner, commit_message):
    editor_user = User.get_editor_user()
    if not editor_user:
        raise EnvironmentError('User Editor not found.')
    user_name_cache = {}
    repository_path = os.path.join(os.getcwd(), get_content_repository_path(owner))
    _actualize_repository(owner.user_name, owner.git_content_repository, owner.git_content_ssh_private_key, repository_path)

    for f in os.listdir(repository_path):
        if f != '.git':
            fpath = os.path.join(repository_path, f)
            if os.path.isdir(fpath):
                shutil.rmtree(fpath)
            else:
                os.remove(fpath)

    for udd in UserDsoDescription.query.filter_by(user_id=editor_user.id):
        cat_name, dso_id = destructuralize_dso_name(udd.deepSkyObject.name)
        dso_dir = _get_dso_dir(cat_name, dso_id)

        repo_file_name = os.path.join(udd.lang_code,'dso', dso_dir, udd.deepSkyObject.name + '.md')
        filename = os.path.join(repository_path, repo_file_name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('name: ' + udd.common_name + '\n')
            f.write('rating: ' + (str(udd.rating) if udd.rating else '') + '\n')
            f.write('create by: ' + _get_user_name(udd.create_by, user_name_cache) + '\n')
            f.write('create date: ' + (str(udd.create_date) if udd.create_date else '') + '\n')
            f.write('update by: ' + _get_user_name(udd.update_by, user_name_cache) + '\n')
            f.write('create date: ' + (str(udd.update_date) if udd.create_date else '') + '\n')
            f.write('---\n')
            f.write(udd.text)

    for uad in UserDsoApertureDescription.query.filter_by(user_id=editor_user.id):
        if not uad.text:
            continue

        cat_name, dso_id = destructuralize_dso_name(uad.deepSkyObject.name)
        dso_dir = _get_dso_dir(cat_name, dso_id)

        repo_file_name = os.path.join(uad.lang_code,'dso', dso_dir, uad.deepSkyObject.name + '_' + uad.aperture_class.replace('/', 'u') + '.md')
        filename = os.path.join(repository_path, repo_file_name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('aperture: ' + uad.aperture_class + '\n')
            f.write('rating: ' + (str(uad.rating) if uad.rating else '') + '\n')
            f.write('create by: ' + _get_user_name(uad.create_by, user_name_cache) + '\n')
            f.write('create date: ' + (str(uad.create_date) if uad.create_date else '') + '\n')
            f.write('update by: ' + _get_user_name(uad.update_by, user_name_cache) + '\n')
            f.write('create date: ' + (str(uad.update_date) if uad.create_date else '') + '\n')
            f.write('---\n')
            f.write(uad.text)

    for ucd in UserConsDescription.query.filter_by(user_id=editor_user.id):
        repo_file_name = os.path.join(ucd.lang_code, 'constellation', ucd.constellation.name + '.md')
        filename = os.path.join(repository_path, repo_file_name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('name: ' + str(ucd.common_name) + '\n')
            f.write('---\n')
            f.write(ucd.text)

    repo = git.Repo(repository_path)
    try:
        with repo.git.custom_environment(GIT_SSH_COMMAND=_get_git_ssh_command(owner.user_name, owner.git_content_ssh_private_key, True)):
            repo.git.add(all=True)
            repo.index.commit(commit_message)
            repo.remotes.origin.push()
    finally:
        _finalize_git_ssh_command(owner.user_name)

def _read_line(f, expected=None, mandatory=False):
    line = f.readline()
    match = re.fullmatch(expected, line)
    return match

def load_public_content_data_from_git(owner):
    editor_user = User.get_editor_user()
    repository_path = os.path.join(os.getcwd(), get_content_repository_path(owner))
    _actualize_repository(owner.user_name, owner.git_content_repository, owner.git_content_ssh_private_key, repository_path)

    for lang_code_dir in [f for f in os.listdir(repository_path) if os.path.isdir(os.path.join(repository_path, f)) and f not in  ['.git', 'images']]:
        _load_dso_descriptions(owner, editor_user, repository_path, lang_code_dir)
        _load_dso_apert_descriptions(owner, editor_user, repository_path, lang_code_dir)
        _load_constellation_descriptions(owner, editor_user, repository_path, lang_code_dir)

    db.session.commit()

def _load_dso_descriptions(owner, editor_user, repository_path, lang_code_dir):
    dso_dir = os.path.join(repository_path, lang_code_dir, 'dso')
    for dso_file in Path(dso_dir).rglob('*.md'):
        dso_name_md = dso_file.name
        if re.match(r'.*?_(\d+u\d+).md$', dso_name_md):
            continue
        with dso_file.open('r') as f:
            dso_name = dso_name_md[:-3]
            _read_line(f, '---\n')
            mname = _read_line(f, r'name:\s*(.*)\n')
            mrating = _read_line(f, r'rating:\s*(.*)\n')
            common_name = mname.group(1) if mname else ''
            rating = mrating.group(1) if mrating else '5'
            _read_line(f, '---\n')
            text = f.read()
            udd = UserDsoDescription.query.filter_by(user_id=owner.id)\
                    .filter_by(lang_code=lang_code_dir) \
                    .join(UserDsoDescription.deepSkyObject, aliased=True) \
                    .filter_by(name=dso_name) \
                    .first()
            if not udd:
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if not dso:
                    continue
                udd = UserDsoDescription(
                    dso_id = dso.id,
                    user_id = editor_user.id,
                    lang_code = lang_code_dir,
                    cons_order = 1,
                    create_by = editor_user.id,
                    create_date = datetime.now(),
                )
            udd.common_name = common_name
            try:
                udd.rating = int(rating)
            except ValueError:
                udd.rating = None
            udd.text = text
            udd.update_by = editor_user.id
            udd.update_date = datetime.now()
            db.session.add(udd)

def _load_dso_apert_descriptions(owner, editor_user, repository_path, lang_code_dir):
    dso_dir = os.path.join(repository_path, lang_code_dir, 'dso')
    for dso_file in Path(dso_dir).rglob('*.md'):
        dso_name_md = dso_file.name
        m = re.match(r'(.*?)_(\d+u\d+).md$', dso_name_md)
        if not m:
            continue
        with dso_file.open('r') as f:
            dso_name = m.group(1)
            _read_line(f, '---\n')
            aperture_class = m.group(2).replace('u','/')
            maperture = _read_line(f, r'aperture:\s*(.*)\n')
            mrating = _read_line(f, r'rating:\s*(.*)\n')
            doc_aperture = maperture.group(1) if maperture else ''
            rating = mrating.group(1) if mrating else '5'
            _read_line(f, '---\n')
            text = f.read()
            uad = UserDsoApertureDescription.query.filter_by(user_id=owner.id)\
                    .filter_by(lang_code=lang_code_dir) \
                    .filter_by(aperture_class=aperture_class) \
                    .join(UserDsoApertureDescription.deepSkyObject, aliased=True) \
                    .filter_by(name=dso_name) \
                    .first()

            if not uad:
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if not dso:
                    continue
                uad = UserDsoApertureDescription(
                    dso_id = dso.id,
                    user_id = editor_user.id,
                    lang_code = lang_code_dir,
                    aperture_class = aperture_class,
                    create_by = editor_user.id,
                    create_date = datetime.now(),
                )
            try:
                uad.rating = int(rating)
            except ValueError:
                uad.rating = None
            uad.text = text
            uad.update_by = editor_user.id
            uad.update_date = datetime.now()
            db.session.add(uad)

def _load_constellation_descriptions(owner, editor_user, repository_path, lang_code_dir):
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
            ucd = UserConsDescription.query.filter_by(user_id=owner.id)\
                    .filter_by(lang_code=lang_code_dir) \
                    .join(UserConsDescription.constellation, aliased=True) \
                    .filter_by(name=constellation_name) \
                    .first()
            if not ucd:
                constellation = Constellation.query.filter_by(name=constellation_name).first()
                if not constellation:
                    continue
                ucd = UserConsDescription(
                    constellation_id = constellation.id,
                    user_id = editor_user.id,
                    lang_code = lang_code_dir,
                    create_by = editor_user.id,
                    create_date = datetime.now(),
                )
            ucd.common_name = common_name
            ucd.text = text
            ucd.update_by = editor_user.id
            ucd.update_date = datetime.now()
            db.session.add(ucd)

def save_personal_data_to_git(owner, commit_message):
    pass

def load_personal_data_from_git(owner):
    pass
