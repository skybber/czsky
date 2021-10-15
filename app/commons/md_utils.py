import re

from flask import current_app
from flask import url_for
from flask import Markup
import commonmark

from app.models import DeepskyObject
from .dso_utils import normalize_dso_name
from .img_dir_resolver import resolve_img_path_dir, parse_inline_link

EXPAND_IMG_DIR_FUNC = re.compile(r'\!\[(.*?)\]\((\$IMG_DIR(.*?))\)')
NO_EXPAND = re.compile(r'(\[.*?\]\(.*?\))|(src=".*)')
EXPANDING_DSOS = re.compile(r'(\W)((M|Abell|NGC|IC)\s*\d+)')


def parse_extended_commonmark(md_text, ignore_name, ext_url_params):
    parsed_text = _expand_img_dir(md_text)
    parsed_text = _auto_links_in_md_text(parsed_text, ignore_name, ext_url_params)
    return commonmark.commonmark(parsed_text)


def _expand_img_dir(md_text):
    result = ''
    prev_end = 0
    for m in re.finditer(EXPAND_IMG_DIR_FUNC, md_text):
        result += md_text[prev_end:m.start()]
        t = m.group(3)
        if t.startswith('/dso'):
            img_dir = resolve_img_path_dir(t[1:])
            if img_dir[1]:
                result += Markup('<figure class="md-fig-left">')
                result += Markup('<img src="{}"/>'.format(m.group(2).replace('$IMG_DIR', img_dir[0])))
                result += Markup('<figcaption>{}</figcaption>'.format(parse_inline_link(img_dir[1])))
                result += Markup('</figure>\n\n')
            else:
                result += Markup(m.group(0).replace('$IMG_DIR', img_dir[0]))
        else:
            result += Markup(m.group(0))
        prev_end = m.end()
    result += md_text[prev_end:]
    # expand rest of non dso images from default img path
    result = Markup(result.replace('$IMG_DIR', current_app.config.get('DEFAULT_IMG_DIR')))
    return result


def _auto_links_in_md_text(md_text, ignore_name, ext_url_params):
    if not md_text:
        return md_text
    result = ''
    prev_end = 0
    cache = {}
    for m in re.finditer(NO_EXPAND, md_text):
        result += _expand_in_subtext(md_text[prev_end: m.start()], ignore_name, cache, ext_url_params)
        result += md_text[m.start():m.end()]
        prev_end = m.end()
    result += _expand_in_subtext(md_text[prev_end:], ignore_name, cache, ext_url_params)
    return result


def _expand_in_subtext(sub_text, ignore_name, cache, ext_url_params):
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
                    replacement = m.group(1) + '[' + m.group(2) + ' ](' + url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name) + ext_url_params + ')'
                cache[dso_name] = replacement
            else:
                replacement = cache[dso_name]
        result += replacement
    result += sub_text[prev_end:]

    return result
