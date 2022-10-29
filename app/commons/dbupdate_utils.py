from datetime import datetime
from app.models import DbUpdate

from app import db


def ask_dbupdate_permit(dbupdate_key, expired_time_delta):
    dbu = DbUpdate.query.filter_by(id=dbupdate_key).first()

    # TODO: make it as atomic update for id and count & result

    if not dbu:
        dbu = DbUpdate()
        dbu.id = dbupdate_key
        dbu.expired = None
        dbu.count = 1

    now = datetime.now()
    if dbu.expired is None or dbu.expired < now:
        dbu.expired = now + expired_time_delta
        dbu.count += 1
        db.session.add(dbu)
        db.session.commit()
        return True

    return False
