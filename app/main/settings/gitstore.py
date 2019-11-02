import os, re

from datetime import datetime
from os import listdir
from os.path import isfile, isdir, join

from flask import current_app

import git

from app import db

from app.models import DeepskyObject, UserDsoDescription

def save_user_data_to_git(owner):
    repository_path = current_app.config.get('USER_DATA_DIR') + '/' + owner.user_name + '/git-repository'
    files = []
    for d in UserDsoDescription.query.filter_by(user_id=owner.id):
        repo_file_name = d.lang_code + '/dso/' + d.deepSkyObject.name + '.md'
        filename = repository_path + '/' + repo_file_name
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            f.write('---\n')
            f.write('name: ' + str(d.common_name) + '\n')
            f.write('rating: ' + str(d.rating) + '\n')
            f.write('---\n')
            f.write(d.text)
        files.append(repo_file_name)

    repo = git.Repo(repository_path)
    repo.index.add(files)
    repo.index.commit("Update")
    origin = repo.remote(name='origin')
    origin.push()

def _read_line(f, expected=None, mandatory=False):
    line = f.readline()
    match = re.fullmatch(expected, line)
    return match

def load_user_data_from_git(owner, editor):
    repository_path = current_app.config.get('USER_DATA_DIR') + '/' + owner.user_name + '/git-repository'
    for lang_code_dir in [f for f in listdir(repository_path) if isdir(join(repository_path, f)) and f != '.git']:
        dso_dir = join(join(repository_path, lang_code_dir), 'dso')
        files = [f for f in listdir(dso_dir) if isfile(join(dso_dir, f))]
        for dso_name_md in files:
            with open(join(dso_dir, dso_name_md), 'r') as f:
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
                        user_id = editor.id,
                        lang_code = lang_code_dir,
                        cons_order = 1,
                        create_by = editor.id,
                        create_date = datetime.now(),
                    )
                dso_description.common_name = common_name
                dso_description.rating = int(rating)
                dso_description.text = text
                dso_description.update_by = editor.id
                dso_description.update_date = datetime.now()
                db.session.add(dso_description)
    db.session.commit()
