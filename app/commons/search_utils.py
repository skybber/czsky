import icu

from datetime import datetime

from flask import request, session
from wtforms.fields import TimeField

from app.commons.pagination import get_page_parameter, get_sortby_parameter
from app.commons.utils import get_lang_and_editor_user_from_request

from app.models import UserConsDescription

cs_collator = icu.Collator.createInstance(icu.Locale('cs_CZ.UTF-8'))

ITEMS_PER_PAGE = 10


def process_paginated_session_search(sess_page_name, sess_sortby_name, sess_arg_form_pairs):
    if request.method == 'POST':
        for pair in sess_arg_form_pairs:
            old_val = session.get(pair[0], None)
            if _field_data_to_serializable(pair[1]) != old_val:
                page = 1
                sort_by = None
                break
        else:
            page = request.args.get(get_page_parameter(), type=int, default=1)
            sort_by = request.args.get(get_sortby_parameter(), None) if sess_sortby_name else None

        session[sess_page_name] = page
        if sess_sortby_name:
            session[sess_sortby_name] = sort_by
        for pair in sess_arg_form_pairs:
            if pair[1].data is not None:
                session[pair[0]] = _field_data_to_serializable(pair[1])
            else:
                session.pop(pair[0], None)
        # is backr necessary ???
        session['is_backr'] = True
        return False, page, sort_by  # post/redirect using backr

    if request.args.get('back', None):
        # is redirect necessary in back???
        session['is_backr'] = True
        return False, None, None  # redirect using backr

    if session.pop('is_backr', False):
        page = session.get(sess_page_name, 1)
        sort_by = session.get(sess_sortby_name, None) if sess_sortby_name else None
        for pair in sess_arg_form_pairs:  # put data from session to form on page action
            _field_data_from_serializable(pair[1], session.get(pair[0], None), pair[0] in session)
    else:
        page = request.args.get(get_page_parameter(), type=int, default=None)
        sort_by = request.args.get(get_sortby_parameter(), None)
        if page is not None:
            session[sess_page_name] = page
            if sess_sortby_name:
                session[sess_sortby_name] = sort_by
            for pair in sess_arg_form_pairs:  # put data from session to form on page action
                _field_data_from_serializable(pair[1], session.get(pair[0], None), pair[0] in session)
        else:
            for pair in sess_arg_form_pairs:
                if pair[1].data is not None:
                    session[pair[0]] = _field_data_to_serializable(pair[1])
                else:
                    if pair[0] != 'items_per_page':
                        session.pop(pair[0], None)
            # session.pop(sess_page_name, 0)
            # for pair in sess_arg_form_pairs: # clear session on initialize GET request
            #     session.pop(pair[0], None)
    if page is None:
        page = 1
    return True, page, sort_by


def _field_data_to_serializable(fld):
    if isinstance(fld, TimeField) and fld.data:
        return fld.data.strftime(fld.format)
    return fld.data


def _field_data_from_serializable(fld, val, set_default):
    if val is not None and isinstance(fld, TimeField):
        fld.data = datetime.strptime(val, fld.format).date()
    if val is None and set_default:
        fld.data = fld.default
    else:
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
        table_sort[sort_by] = {'sort': prefix + sort_by, 'icon': icon}
    return table_sort


def get_catalogues_menu_items():
    return [
         ('M', 'Messier'),
         ('NGC', 'NGC'),
         ('IC', 'IC'),
         ('Abell', 'Abell'),
         ('Sh2', 'Sharpness'),
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


def get_packed_constell_list():
    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)

    if editor_user:
        constellation_id_names = UserConsDescription.query \
            .with_entities(UserConsDescription.constellation_id, UserConsDescription.common_name) \
            .filter_by(user_id=editor_user.id, lang_code=lang).all()
    else:
        constellation_id_names = []

    constellation_id_names = sorted(constellation_id_names, key=lambda x: cs_collator.getSortKey(x[1]))

    packed_constell_list = []
    letter, letter_list = '', []
    l1, l2 = None, None
    for constel in constellation_id_names:
        if constel[1][0] != letter:
            if l2 and letter_list:
                packed_constell_list.append([l1+' ... '+l2, letter_list])
                letter_list = []
                l1, l2 = None, None
            letter = constel[1][0]
            if l1 is None:
                l1 = letter
            else:
                l2 = letter
        letter_list.append(constel)

    if letter_list:
        if l2 is not None:
            packed_constell_list.append([l1+' ... '+l2, letter_list])
        else:
            packed_constell_list.append([l1, letter_list])
    return packed_constell_list


def get_order_by_field(sort_def, sort_by):
    order_by_field = None
    if sort_by:
        desc = sort_by[0] == '-'
        sort_by_name = sort_by[1:] if desc else sort_by
        order_by_field = sort_def.get(sort_by_name)
        if order_by_field and desc:
            order_by_field = order_by_field.desc()
    return order_by_field
