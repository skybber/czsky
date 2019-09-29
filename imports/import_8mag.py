#!/usr/bin/python

import sys, re, getopt, os, glob, pathlib
import sqlite3
import hashlib

from bs4 import BeautifulSoup

from sqlalchemy.exc import IntegrityError
from json.decoder import JSONDecodeError

from app import db
from app.models.user import User
from app.models.constellation import Constellation, UserConsDescription
from googletrans import Translator

translator_stopped = False

def checkdir(dir, param):
    if not os.path.exists(dir) or not os.path.isdir(dir):
        print('error: -' + param + ': existing directory expected.')
        usage()
        return False;
    return True

def usage():
    print('Usage : import_8mag.py.py --src_path path_to_8mag_files --debug')

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



def do_translate(translator, db_connection, ptext):
    global translator_stopped

    if not db_connection or not translator:
        return ptext

    hashv = hashlib.md5(ptext.encode('utf-8')).hexdigest()
    cur = db_connection.cursor()
    sqlqry = "SELECT text FROM translations WHERE hash=:1;"
    c = cur.execute(sqlqry, [hashv])
    c = c.fetchone();
    trans_text = c[0] if c else None
    if trans_text:
        return trans_text

    if translator_stopped:
        return ptext

    try:
        trans_text = translator.translate(ptext, src='sk', dest='cs').text
        icur = db_connection.cursor()
        icur.execute('insert into translations values (?,?)', [hashv, trans_text])
        db_connection.commit()
        icur.close()
    except JSONDecodeError:
        print('Translation failed text=' + ptext)
        print('Automatic translator stopped.')
        translator_stopped = True
        trans_text = ptext
    finally:
        cur.close()
    return trans_text


def extract_div_elem(translator, db_connection, div_elem):
    md_text = ''
    for elem in div_elem.find_all(['p', 'img']):
        if elem.name == 'p':
            elem.find()
            ptext = elem.text.strip()
            if len(ptext) > 0:
                md_text += do_translate(translator, db_connection, ptext) + '\n\n'
        else:
            src = elem['src']
            if src.startswith('./'):
                src = src[2:]
            src = src.replace('(', '_').replace(')', '_').replace(' ', '_')
            md_text += '![](/static/webassets-external/users/8mag/cons/' + src + ')\n\n'
    return md_text

def extract_cons_objects(translator, soup, db_connection):
    md_text = ''
    # exponaty , 'zaujimave_objekty', 'challange_objekty', 'priemerne_objekty', 'asterismy'
    elems = soup.find_all( [ 'a', 'h4', 'div' ])
    part = None
    for elem in elems:
        if elem.name == 'a':
            if elem.has_attr('id') and elem['id'] in ['exponaty' , 'zaujimave_objekty', 'challange_objekty', 'priemerne_objekty', 'asterismy']:
                part = elem['id']
                md_text += '### ' + do_translate(translator, db_connection, elem.text.strip()) + '\n\n'
                continue
            else:
                continue
        elif not part:
            continue
        if elem.name == 'h4':
            md_text += '#### ' + do_translate(translator, db_connection, elem.text.strip()) + '\n\n'
        elif elem.name == 'div' and elem.has_attr('class') and 'level4' in elem['class']:
            md_text += extract_div_elem(translator, db_connection, elem) + '\n\n'

    return md_text

def do_import_8mag(src_path, debug_log, translation_db_name):

    user_8mag = User.query.filter_by(email='8mag').first()

    if not user_8mag:
        print('User 8mag not found.')
        sys.exit(2)

    UserConsDescription.query.filter_by(user_id=user_8mag.id).delete()

    db_connection = None
    try:
        db_connection = sqlite3.connect(translation_db_name)
    except Exception:
        print('Connection to db="' + translation_db_name + '" failed. Translations will not be used.')

    translator = Translator()

    files = [f for f in sorted(glob.glob(src_path + '/*.htm'))]
    for f in files:
        if debug_log:
            print('Processing: ' + f)
        with open(f, 'r') as ifile:
            data = ifile.read()
            soup = BeautifulSoup(data, 'html.parser')
            for strong in soup.find_all(['strong']):
                strong.string.insert_before('**')
                strong.insert_after('**')

            header = soup.select_one('h1')
            if header:
                cons_name = soup.select_one('h1').text.strip()
                lat_name = cons_name[cons_name.find('(') + 1: cons_name.find(')')].strip().lower()
                if lat_name == 'ursa maior':
                    lat_name = 'ursa major'
                cons = Constellation.query.filter_by(name=lat_name).first()
                if not cons:
                    print('Constellation "' + lat_name + '" not fount in db!')
                    continue
                # md_text = '## ' + cons_name + '\n\n'

                translator_was_stopped = False
                if not translator_stopped:
                    md_text = extract_div_elem(translator, db_connection, soup.select_one('div.level1'))
                    md_text += extract_div_elem(translator, db_connection, soup.select_one('div.level2'))
                    md_text += extract_cons_objects(translator, soup, db_connection)

                    ucd = UserConsDescription(
                        constellation_id = cons.id,
                        user_id = user_8mag.id,
                        text = md_text,
                        lang_code = 'cs'
                        )
                    db.session.add(ucd)
                    translator_was_stopped = translator_stopped

                if not translator_was_stopped:
                    md_text = extract_div_elem(translator, db_connection, soup.select_one('div.level1'))
                    md_text += extract_div_elem(translator, db_connection, soup.select_one('div.level2'))
                    md_text += extract_cons_objects(translator, soup, db_connection)

                    ucd = UserConsDescription(
                        constellation_id = cons.id,
                        user_id = user_8mag.id,
                        text = md_text,
                        lang_code = 'sk'
                        )
                    db.session.add(ucd)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()

    if db_connection:
        db_connection.close()

