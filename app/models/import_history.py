from enum import Enum
import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext

from .. import db


from app.commons.form_utils import FormEnum


class ImportType(Enum):
    OBSERVATION = 'OBSERVATION'
    SESSION_PLAN = 'SESSION_PLAN'

    def loc_text(self):
        if self == ImportType.OBSERVATION:
            return lazy_pgettext('importtype', 'Observation')
        if self == ImportType.SESSION_PLAN:
            return lazy_pgettext('importtype', 'Session Plan')
        return ''


class ImportHistoryRecStatus(Enum):
    PROCESSING = 'PROCESSING'
    IMPORTED = 'IMPORTED'
    DELETED = 'DELETED'

    def loc_text(self):
        if self == ImportHistoryRecStatus.PROCESSING:
            return lazy_pgettext('importstatus', 'Processing')
        if self == ImportHistoryRecStatus.IMPORTED:
            return lazy_pgettext('importstatus', 'Imported')
        if self == ImportHistoryRecStatus.DELETED:
            return lazy_pgettext('importstatus', 'Deleted')
        return ''


class ImportHistoryRec(db.Model):
    __tablename__ = 'import_history_recs'
    id = db.Column(db.Integer, primary_key=True)
    import_type = db.Column(sqlalchemy.Enum(ImportType))
    status = db.Column(sqlalchemy.Enum(ImportHistoryRecStatus))
    log = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
