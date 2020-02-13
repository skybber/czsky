import re
import os

from flask import current_app
from flask import url_for
import commonmark

from app.models import DeepskyObject
from .dso_utils import normalize_dso_name

EXPAND_IMG_DIR_FUNC = re.compile(r'\(\$IMG_DIR(.*?)\)')
IGNORING_AREAS = re.compile(r'\[.*?\]\(.*?\)')
EXPANDING_DSOS = re.compile(r'(\W)((M|Abell|NGC|IC)\s*\d+)')

def parse_extended_commonmark(md_text, ignore_name):
    parsed_text = _expand_img_dir(md_text)
    parsed_text = _auto_links_in_md_text(parsed_text, ignore_name)
    return commonmark.commonmark(parsed_text)

def _expand_img_dir(md_text):
    img_dir = current_app.config.get('IMG_DIR')
    result = ''
    prev_end = 0
    for m in re.finditer(EXPAND_IMG_DIR_FUNC, md_text):
        result += md_text[prev_end:m.start()]
        t = m.group(1)
        replaced = False
        if t.startswith('/dso') and not os.path.exists('app' + os.path.join(img_dir, t[1:])):
            start = t.rfind('/')
            if start >= 0:
                image = t[start+1:]
                alternernative_image = 'app' + os.path.join(img_dir, 'dso', 'ngcic', image)
                if os.path.exists(alternernative_image):
                    result += '(' + img_dir + 'dso/ngcic/' + image + ')'
                    replaced = True
        if not replaced:
            result += m.group(0)
        prev_end = m.end()
    result += md_text[prev_end:]
    result = result.replace('$IMG_DIR', img_dir)
    return result


def _auto_links_in_md_text(md_text, ignore_name):
    if not md_text:
        return md_text
    result = ''
    prev_end = 0
    cache = {}
    for m in re.finditer(IGNORING_AREAS, md_text):
        result += _expand_in_subtext(md_text[prev_end: m.start()], ignore_name, cache)
        result += md_text[m.start():m.end()]
        prev_end = m.end()
    result += _expand_in_subtext(md_text[prev_end:], ignore_name, cache)
    return result

def _expand_in_subtext(sub_text, ignore_name, cache):
    result = ''
    prev_end = 0
    for m in re.finditer(EXPANDING_DSOS, sub_text):
        result += sub_text[prev_end:m.start()]
        prev_end = m.end()
        dso_name = normalize_dso_name(m.group(2))
        replacement = m.group(0)
        if dso_name != ignore_name:
            if dso_name not in cache:
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if dso:
                    replacement = m.group(1) + '[' + m.group(2) + ' ](' + url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.id) + ')'
                cache[dso_name] = replacement
            else:
                replacement = cache[dso_name]
        result += replacement
    result += sub_text[prev_end:]

    return result
