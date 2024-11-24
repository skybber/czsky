import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext

from app.commons.form_utils import FormEnum
from .. import db


class DefaultThemeType(FormEnum):
    DARK = 'DARK'
    LIGHT = 'LIGHT'
    NIGHT = 'NIGHT'

    def loc_text(self):
        if self == DefaultThemeType.DARK:
            return lazy_pgettext('theme_type', 'Dark')
        if self == DefaultThemeType.LIGHT:
            return lazy_pgettext('theme_type', 'Light')
        if self == DefaultThemeType.NIGHT:
            return lazy_pgettext('theme_type', 'Night')
        return ''


class ChartTheme(db.Model):
    __tablename__ = 'chart_themes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    default_type = db.Column(sqlalchemy.Enum(DefaultThemeType))
    definition = db.Column(db.Text)
    order = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    is_active = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
