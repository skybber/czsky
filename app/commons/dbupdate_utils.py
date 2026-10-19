from datetime import datetime, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError

from app.models import DbUpdate

from app import db


def _utcnow():
    # DbUpdate.expired is a naive DateTime column; store UTC in it.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_dbupdate_row(dbupdate_key):
    if db.session.get(DbUpdate, dbupdate_key) is not None:
        return
    try:
        db.session.add(DbUpdate(id=dbupdate_key, expired=None, count=0))
        db.session.commit()
    except IntegrityError:
        # Another process created the row first.
        db.session.rollback()


def ask_dbupdate_permit(dbupdate_key, expired_time_delta):
    """
    Atomically claims the job identified by dbupdate_key for expired_time_delta.

    Returns True for exactly one caller until the claim expires, even when the same
    scheduled job fires concurrently in several processes. expired_time_delta must be
    shorter than the job's schedule interval minus its jitter, otherwise regular runs
    get skipped.
    """
    _ensure_dbupdate_row(dbupdate_key)

    now = _utcnow()
    result = db.session.execute(
        update(DbUpdate)
        .where(DbUpdate.id == dbupdate_key)
        .where(or_(DbUpdate.expired.is_(None), DbUpdate.expired < now))
        .values(expired=now + expired_time_delta, count=DbUpdate.count + 1)
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    return result.rowcount == 1
