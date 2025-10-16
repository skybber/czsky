from flask import (
    session,
)
from flask_login import current_user


def allow_view_session_plan(session_plan):
    if not session_plan:
        return False
    if not session_plan.is_public:
        if current_user.is_anonymous:
            if not session_plan.is_anonymous or session.get('session_plan_id') != session_plan.id:
                return False
        elif session_plan.user_id != current_user.id:
            return False
    return True


def allow_view_user_object_list(user_object_list):
    if not user_object_list:
        return False

    if not user_object_list.is_public:
        if user_object_list.user_id != current_user.id:
            return False
    return True

