import re

from flask import url_for

from app.models import DeepskyObject
from .dso_utils import normalize_dso_name

ignoring_areas = re.compile(r'\[.*?\]\(.*?\)')

expanding_dsos = re.compile(r'(\W)((M|Abell|NGC|IC)\s*\d+)')

def auto_links_in_md_text(md_text, ignore_name):
    if not md_text:
        return md_text
    result = ''
    prev_end = 0
    cache = {}
    for m in re.finditer(ignoring_areas, md_text):
        result += _expand_in_subtext(md_text[prev_end: m.start()], ignore_name, cache)
        result += md_text[m.start():m.end()]
        prev_end = m.end()
    result += _expand_in_subtext(md_text[prev_end:], ignore_name, cache)
    return result

def _expand_in_subtext(sub_text, ignore_name, cache):
    result = ''
    prev_end = 0
    for m in re.finditer(expanding_dsos, sub_text):
        result += sub_text[prev_end:m.start()]
        prev_end = m.end()
        dso_name = normalize_dso_name(m.group(2))
        replacement = m.group(2)
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
