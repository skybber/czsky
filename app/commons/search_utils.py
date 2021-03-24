from datetime import datetime

from flask import (
    request,
    session,
)
from wtforms.fields import (
    TimeField,
)

from flask_babel import lazy_gettext

from app.commons.pagination import get_page_parameter

ITEMS_PER_PAGE = 10

def process_paginated_session_search(sess_page_name, sess_arg_form_pairs):
    if request.method == 'POST':
        for pair in sess_arg_form_pairs:
            old_val = session.get(pair[0], None)
            if _field_data_to_serializable(pair[1]) != old_val:
                page = 1
                break
        else:
            page = request.args.get(get_page_parameter(), type=int, default=1)

        session[sess_page_name] = page
        for pair in sess_arg_form_pairs:
            if pair[1].data is not None:
                session[pair[0]] = _field_data_to_serializable(pair[1])
            else:
                session.pop(pair[0], None)
        # is backr necessary ???
        session['is_backr'] = True
        return (False, page, ) # post/redirect using backr

    if request.args.get('back', None):
        # is redirect necessary in back???
        session['is_backr'] = True
        return (False, None, )  # redirect using backr

    if session.pop('is_backr', False):
        page = session.get(sess_page_name, 1)
        for pair in sess_arg_form_pairs: # put data from session to form on page action
            _field_data_from_serializable(pair[1], session.get(pair[0], None))
    else:
        page = request.args.get(get_page_parameter(), type=int, default=None)
        if page is not None:
            session[sess_page_name] = page
            for pair in sess_arg_form_pairs: # put data from session to form on page action
                _field_data_from_serializable(pair[1], session.get(pair[0], None))
#         else:
#             session.pop(sess_page_name, 0)
#             for pair in sess_arg_form_pairs: # clear session on initialize GET request
#                 session.pop(pair[0], None)
    if page is None:
        page = 1
    return (True, page,)


def _field_data_to_serializable(fld):
    if isinstance(fld, TimeField) and fld.data:
        return fld.data.strftime(fld.format)
    return fld.data


def _field_data_from_serializable(fld, val):
    if val is not None and isinstance(fld, TimeField):
        fld.data = datetime.strptime(val, fld.format).date()
    fld.data = val


def process_session_search(sess_arg_form_pairs):
    if request.method == 'POST':
        for pair in sess_arg_form_pairs:
            if pair[1].data:
                session[pair[0]] = pair[1].data
            else:
                session.pop(pair[0], None)
        session['is_backr'] = True
        return False

    if request.args.get('back', None):
        session['is_backr'] = True
        for pair in sess_arg_form_pairs:
            pair[1].data = session.get(pair[0], None)
        return False

    if session.pop('is_backr', False):
        for pair in sess_arg_form_pairs:
            pair[1].data = session.get(pair[0], None)

    return True


def get_items_per_page(items_per_page):
    if request.method == 'GET':
        items_per_page.data = session.get('items_per_page', None)
        if not items_per_page.data:
            items_per_page.data = ITEMS_PER_PAGE
    else:
        session['items_per_page'] = items_per_page.data
    return items_per_page.data

def create_table_sort(current_sort_by, table_columns):
    if current_sort_by:
        if current_sort_by[0] == '-':
            current_sort_by_name = current_sort_by[1:]
            current_sort_by_direction = '-'
        else:
            current_sort_by_name = current_sort_by
            current_sort_by_direction = ''
    else:
        current_sort_by_name = ''
        current_sort_by_direction = ''

    table_sort = {}
    for sort_by in table_columns:
        if sort_by == current_sort_by_name:
            if current_sort_by_direction == '':
                prefix = '-'
                icon = '<i class="caret down icon"></i>'
            else:
                prefix = ''
                icon = '<i class="caret up icon"></i>'
        else:
            prefix = ''
            icon = ''
        table_sort[sort_by] = { 'sort': prefix + sort_by, 'icon': icon}
    return table_sort

def get_catalogues_menu_items():
    return [
         ('M', 'Messier'),
         ('NGC', 'NGC'),
         ('IC', 'IC'),
         ('Abell','Abell'),
         ('Sh2','Sharpless'),
         ('HCG', 'Hickson'),
         ('B', 'Barnard'),
         ('Cr', 'Collinder'),
         ('Pal', 'Palomar'),
         ('PK', 'Perek-Kohoutek'),
         ('Stock', 'Stock'),
         ('UGC', 'UGC'),
         ('Mel', 'Melotte'),
         ('LDN', 'LDN'),
         ('VIC', 'Vic'),
    ]
