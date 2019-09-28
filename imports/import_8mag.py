#!/usr/bin/python

import sys, re, getopt, os, glob, pathlib

from bs4 import BeautifulSoup

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user import User
from app.models.constellation import Constellation, UserConsDescription

def checkdir(dir, param):
    if not os.path.exists(dir) or not os.path.isdir(dir):
        print("error: -" + param + ": existing directory expected.")
        usage()
        return False;
    return True

def usage():
    print("Usage : import_8mag.py.py --src_path path_to_8mag_files --debug")

def main():
    src_path = None
    dst_path = None
    debug_log = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['src_path=','dst_path=', 'debug'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, a in opts:
        if o == '--src_path':
            src_path = a
        if o == '--dst_path':
            dst_path = a
        elif o == '--debug':
            debug_log = True

    if src_path is None or dst_path is None:
        usage()
        sys.exit(2)

    if not dst_path.endswith('/'):
        dst_path += '/'

    if not checkdir(src_path, 'src_path'):
        sys.exit(2)

    if not checkdir(dst_path, 'dst_path'):
        sys.exit(2)

    do_import_8mag(src_path, dst_path, debug_log)

def do_import_8mag(src_path, dst_path, debug_log):

    user_8mag = User.query.filter_by(email='8mag').first()

    if not user_8mag:
        print('User 8mag not found.')
        sys.exit(2)

    os.makedirs(dst_path, exist_ok=True)

    files = [f for f in glob.glob(src_path + "/*.htm")]
    for f in files:
        if debug_log:
            print('Processing: ' + f)
        with open(f, 'r') as ifile:
            data = ifile.read()
            soup = BeautifulSoup(data, 'html.parser')
            header = soup.select_one('h1')
            if header:
                cons_name = soup.select_one('h1').text.strip()
                lat_name = cons_name[cons_name.find('(') + 1: cons_name.find(')')].strip().lower()
                cons = Constellation.query.filter_by(name=lat_name).first()
                if not cons:
                    print('Constellation "' + lat_name + '" not fount in db!')
                    continue
                md_text = '## ' + cons_name + '\n\n'
                level_1 = soup.select_one('div.level1')
                level_1.find_all(['p', 'img'])
                for elem in level_1.find_all(['p', 'img']):
                    if elem.name == 'p':
                        ptext = elem.text.strip()
                        if len(ptext) > 0:
                            md_text += elem.text.strip() + '\n\n'
                    else:
                        src = elem['src']
                        if src.startswith('./'):
                            src = src[2:]
                        md_text += '![](/static/webassets-external/users/8mag/cons/' + src + ')\n\n'
                # of = dst_path + f[f.rfind('/') + 1:].replace('.htm', '.md')

                # with open(of, 'w') as ofile:
                #    ofile.write(md_text)

                ucd = UserConsDescription(
                    constellation_id = cons.id,
                    user_id = user_8mag.id,
                    text = md_text
                    )
                db.session.add(ucd)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()

