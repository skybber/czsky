#!/usr/bin/python

import sys, re, getopt, os, glob, pathlib, time, csv
import sqlite3
import hashlib
import imghdr
from shutil import copyfile
from os.path import join
from pathlib import Path

from datetime import datetime

from bs4 import BeautifulSoup

from sqlalchemy.exc import IntegrityError
from json.decoder import JSONDecodeError

from app import db
from app.models.user import User
from app.models.constellation import Constellation, UserConsDescription
from app.models.deepskyobject import DeepskyObject, UserDsoDescription
from app.models.star import UserStarDescription
from app.commons.dso_utils import normalize_dso_name
from googletrans import Translator

translation_cnt = 0
translator_stopped = False

rating_map = { 'exponaty' : 10 , 'zaujimave_objekty' : 8, 'challange_objekty': 6, 'priemerne_objekty' : 4, 'asterismy' : 10}

vic_catalogue = {}

dso_img_map = {}

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


def fix_bold(text):
    index1 = text.find('** ')
    while index1 >= 0:
        index2 = text.find(' **', index1)
        if index2 < 0:
            break
        text = text[:index1] + '**' + text[index1 + 3:index2] + '**' + text[index2+3:]
        index1 = text.find('** ', index2 + (3-2))
    return text


def do_translate(translator, db_connection, ptext):
    global translator_stopped
    global translation_cnt

    if not db_connection or not translator:
        return ptext

    hashv = hashlib.md5(ptext.encode('utf-8')).hexdigest()
    cur = db_connection.cursor()
    sqlqry = "SELECT text FROM translations WHERE hash=:1;"
    c = cur.execute(sqlqry, [hashv])
    c = c.fetchone();
    trans_text = c[0] if c else None
    if trans_text:
        trans_text = fix_bold(trans_text)
        trans_text = trans_text.replace('triedry', 'triedru').replace('zväčení', 'zvětšení')
        return trans_text

    if translator_stopped:
        return ptext

    try:
        trans_text = translator.translate(ptext, src='sk', dest='cs').text
        trans_text = fix_bold(trans_text)
        trans_text = trans_text.replace('triedry', 'triedru').replace('zväčení', 'zvětšení')
        translation_cnt += 1
        if translation_cnt >= 10:
            print('Sleeping for 10s after bulk translations...')
            time.sleep(10)
            translation_cnt = 0
        else:
            time.sleep(1)
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


def extract_div_elem(translator, db_connection, src_path, div_elem, img_name=None, is_cons=False):
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

            subdir = 'cons/' if is_cons else 'dso/'
            static_path = '/static/webassets-external/users/8mag/img/'
            path = Path('app' + static_path + subdir)
            path.mkdir(parents=True, exist_ok=True)
            old_img_file = join(src_path, src)

            if img_name and not img_name.startswith('ASTER_'):
                img_type = imghdr.what(old_img_file)
                if img_type == 'jpeg':
                    img_type = 'jpg'
                new_img_name = img_name
                counter = 1
                while new_img_name in dso_img_map and dso_img_map[new_img_name] != src:
                    new_img_name = img_name + '_' + str(counter)
                    counter += 1
                dso_img_map[new_img_name] =src
                new_img_file = static_path + subdir + new_img_name + '.' + img_type
                if os.path.isfile(old_img_file):
                    copyfile(old_img_file, 'app/' + new_img_file)
                md_text += '![<](' + new_img_file + ')\n'
            else:
                new_img_file = static_path + subdir + src[src.rfind('/'):]
                if os.path.isfile(old_img_file):
                    copyfile(old_img_file, 'app/' + new_img_file)
                md_text += '![<](' + new_img_file + ')\n'
    return md_text

def save_star_descriptions(translator, db_connection, src_path, div_elem, user_8mag, lang_code, cons):
    for elem in div_elem.find_all('p'):
        elem.find()
        ptext = elem.text.strip()
        if len(ptext) > 0:
            if ptext.startswith('**'):
                end = ptext.find('**', 2)
                name = ptext[2:end]
                text = ptext[end + 2:].strip()
                while text.startswith('–') or text.startswith('-'):
                    text = text[1:].strip()
                if len(text) > 0:
                    text = do_translate(translator, db_connection, text)
                usd = UserStarDescription(
                    constellation_id = cons.id,
                    common_name = name,
                    user_id = user_8mag.id,
                    lang_code = lang_code,
                    text = text,
                    create_by = user_8mag.id,
                    update_by = user_8mag.id,
                    create_date = datetime.now(),
                    update_date = datetime.now(),
                )
                db.session.add(usd)

def save_dso_descriptions(translator, src_path, soup, db_connection, user_8mag, lang_code, cons):
    # exponaty , 'zaujimave_objekty', 'challange_objekty', 'priemerne_objekty', 'asterismy'
    elems = soup.find_all( [ 'a', 'h4', 'div' ])
    part = None
    rating = None
    found_objects = []
    cons_order = 0
    for elem in elems:
        if elem.name == 'a':
            if elem.has_attr('id') and elem['id'] in ['exponaty' , 'zaujimave_objekty', 'challange_objekty', 'priemerne_objekty', 'asterismy']:
                part = elem['id']
                rating = rating_map[part]
                dso_text = ''
                dso_name = ''
                dso_common_name = ''
                cons_order += 1
                continue
            else:
                continue
        elif not part:
            continue
        if elem.name == 'h4':
            dso_text = ''
            dso_name = ''
            dso_common_name = ''
            if part == 'asterismy':
                dso_name = 'ASTER_' + elem.text.strip()
                found_objects.append({'names' : [dso_name]})
            else:
                dso_name = elem.text.strip()
                if '(' in dso_name:
                    if ')' in dso_name:
                        dso_common_name = dso_name[dso_name.index('(') + 1 : dso_name.index(')')].strip()
                        if '–' in dso_common_name:
                            dso_common_name = dso_common_name[dso_common_name.index('–') + 1:].strip()
                        else:
                            if dso_common_name.startswith('NGC'):
                                dso_common_name = ''
                    dso_name = dso_name[:dso_name.index('(')]
                if dso_name.startswith('Sharpless 2-'):
                    dso_name = 'SH2-' + dso_name[len('Sharpless 2-'):]
                elif dso_name.startswith('Collinder'):
                    dso_name = 'Cr' + dso_name[len('Collinder'):]
                elif dso_name.startswith('Melotte'):
                    dso_name = 'Mel' + dso_name[len('Melotte'):]
                elif dso_name.startswith('Palomar'):
                    dso_name = 'Pal' + dso_name[len('Palomar'):]
                elif dso_name.startswith('Barnard'):
                    dso_name = 'B' + dso_name[len('Barnard'):]
                dso_name = normalize_dso_name(dso_name.strip())
                others = []
                if dso_name == 'Stephanov kvintet':
                    dso_name = 'NGC7318'
                    others = ['NGC7320', 'NGC7319', 'NGC7317' ]
                elif dso_name.startswith('NGC') and any(x in dso_name for x in ['-', '/', '&', 'A']):
                    if '-' in dso_name:
                        dso_items = dso_name.split('-')
                    elif '/' in dso_name:
                        dso_items = dso_name.split('/')
                    elif '&' in dso_name:
                        dso_items = dso_name.split('&')
                    elif 'A' in dso_name:
                        dso_items = dso_name.split('A')
                        dso_items = dso_items[:-1]
                    dso_name = dso_items[0]
                    if dso_name.endswith('A'):
                        dso_name = dso_name[:-1]
                    if dso_name == 'NGC978':
                        dso_name = 'NGC0978A'
                    dso_name = normalize_dso_name(dso_name)
                    for other in dso_items[1:]:
                        others.append(dso_name[:-len(other)] + other)
                found_objects.append({'names' : [dso_name] + others, 'rating': rating, 'dso_common_name': dso_common_name })
        elif elem.name == 'div' and elem.has_attr('class') and 'level4' in elem['class']:
            if dso_name:
                t = None if dso_name.startswith('ASTER_') else translator
                dso_text += extract_div_elem(t, db_connection, src_path, elem, img_name = dso_name) + '\n\n'
                found_objects[-1]['text'] = dso_text

    for m in found_objects:
        if m['names'][0].startswith('ASTER_'):
            vic_cs_name = m['names'][0][len('ASTER_'):].strip()
            vic_catalogue_row = vic_catalogue.get(vic_cs_name, None)
            if vic_catalogue_row:
                vic_id = vic_catalogue_row['Vic#'].strip()
                if len(vic_id) < 2:
                    vic_id = '0' + vic_id
                dso_name = 'VIC' + vic_id
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if dso:
                    # update constellation ID since it is missing in vic catalogue
                    dso.constellation_id = cons.id
                    db.session.add(dso)

                    text = m['text'] + '\n'
                    text += '##### 10x50 : ' + vic_catalogue_row.get('10x50', '') + '\n'
                    text += '##### 15x70 :' + vic_catalogue_row.get('15x70', '') + '\n'
                    text += '##### 25x100 : ' + vic_catalogue_row.get('25x100', '') + '\n'

                    rating = vic_catalogue_row['10x50'].find('☆')
                    if rating < 0:
                        rating = 5;
                    udd = UserDsoDescription(
                        dso_id = dso.id,
                        user_id = user_8mag.id,
                        rating = rating,
                        lang_code = lang_code,
                        cons_order = cons_order,
                        text = text,
                        common_name = vic_catalogue_row.get('name_cs', ''),
                        create_by = user_8mag.id,
                        update_by = user_8mag.id,
                        create_date = datetime.now(),
                        update_date = datetime.now(),

                    )
                    db.session.add(udd)
                else:
                    print('Deepsky object not found. dso name=' + dso_name)
            else:
                print('VIC object not found. cs name=' + vic_cs_name)
        else:
            for dso_name in m['names']:
                dso = DeepskyObject.query.filter_by(name=m['names'][0]).first()
                if dso:
                    udd = UserDsoDescription(
                        dso_id = dso.id,
                        user_id = user_8mag.id,
                        rating = m['rating'],
                        lang_code = lang_code,
                        cons_order = cons_order,
                        text = m['text'],
                        common_name = m['dso_common_name'],
                        create_by = user_8mag.id,
                        update_by = user_8mag.id,
                        create_date = datetime.now(),
                        update_date = datetime.now(),
                        )
                    db.session.add(udd)
                else:
                    print('Deepsky object not found. dso name=' + m['names'][0])

def do_import_8mag(src_path, debug_log, translation_db_name, vic_8mag_file):

    user_8mag = User.query.filter_by(user_name='8mag').first()

    if not user_8mag:
        print('User 8mag not found.')
        return

    UserConsDescription.query.filter_by(user_id=user_8mag.id).delete()

    db_connection = None
    try:
        db_connection = sqlite3.connect(translation_db_name)
    except Exception:
        print('Connection to db="' + translation_db_name + '" failed. Translations will not be used.')

    with open(vic_8mag_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        for row in reader:
            vic_catalogue[row['name_cs'].strip()] = row

    translator = Translator(service_urls=[ 'translate.google.cn', ] )

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

                if not translator_stopped:
                    md_text = extract_div_elem(translator, db_connection, src_path, soup.select_one('div.level1'), cons.iau_code, is_cons=True)
                    if not translator_stopped:
                        save_star_descriptions(translator, db_connection, src_path, soup.select_one('div.level2'), user_8mag, 'cs', cons)

                    if not translator_stopped:
                        ucd = UserConsDescription(
                            constellation_id = cons.id,
                            user_id = user_8mag.id,
                            common_name = cons_name,
                            text = md_text,
                            lang_code = 'cs',
                            create_by = user_8mag.id,
                            update_by = user_8mag.id,
                            create_date = datetime.now(),
                            update_date = datetime.now(),
                            )
                        db.session.add(ucd)

                        save_dso_descriptions(translator, src_path, soup, db_connection, user_8mag, 'cs', cons)

                md_text = extract_div_elem(None, db_connection, src_path, soup.select_one('div.level1'), cons.iau_code, is_cons=True)
                save_star_descriptions(None, db_connection, src_path, soup.select_one('div.level2'), user_8mag, 'sk', cons)

                ucd = UserConsDescription(
                    constellation_id = cons.id,
                    user_id = user_8mag.id,
                    common_name = cons_name,
                    text = md_text,
                    lang_code = 'sk',
                    create_by = user_8mag.id,
                    update_by = user_8mag.id,
                    create_date = datetime.now(),
                    update_date = datetime.now(),
                    )
                db.session.add(ucd)
                save_dso_descriptions(None, src_path, soup, db_connection, user_8mag, 'sk', cons)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    print('Error')

    if db_connection:
        db_connection.close()

