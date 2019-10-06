from flask import (
    request,
    session,
)

from app.commons.pagination import get_page_parameter

def process_paginated_session_search(sess_page_name, sess_arg_form_pairs):
    back = request.args.get('back', None)
    ret = []
    if back:
        page = session.get(sess_page_name, 1)
        ret.append(page)
        for pair in sess_arg_form_pairs: # put data from session to form on back action
            stored_search = session.get(pair[0], None)
            pair[1].data = stored_search
            ret.append(stored_search)
    else:
        page = request.args.get(get_page_parameter(), type=int, default=1)
        if request.method == 'GET':
            if get_page_parameter() in request.args:
                ret.append(page)
                session[sess_page_name] = page
                for pair in sess_arg_form_pairs: # put data from session to form on page action
                    stored_search = session.get(pair[0], None)
                    pair[1].data = stored_search
                    ret.append(stored_search)
            else:
                ret.append(1)
                session.pop(sess_page_name, 0)
                for pair in sess_arg_form_pairs: # clear session on initialize GET request
                    session.pop(pair[0], None)
                    ret.append(None)
        else:
            for pair in sess_arg_form_pairs:
                old_val = session.get(pair[0], None)
                if pair[1].data != old_val:
                    page = 1
                    break

            ret.append(page)
            session[sess_page_name] = page
            for pair in sess_arg_form_pairs:
                if pair[1].data:
                    search = pair[1].data
                    session[pair[0]] = search
                    ret.append(search)
                else:
                    session.pop(pair[0], None)
                    ret.append(None)
    return ret