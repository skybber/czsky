from app import db


def process_delete_account(user):
    user.user_name = user.user_name + '__deleted__'
    user.email = user.email + '__deleted__'
    user.is_deleted = True
    db.session.add(user)
    db.session.commit()
    return True