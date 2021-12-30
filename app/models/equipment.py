import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext

from .. import db

from app.commons.form_utils import FormEnum


class TelescopeType(FormEnum):
    REFRACTOR = 'REFRACTOR'
    REFLECTOR = 'REFLECTOR'
    OTHER = 'OTHER'

    def loc_text(self):
        if self == TelescopeType.REFRACTOR:
            return lazy_pgettext('telescope_type', 'Refractor')
        if self == TelescopeType.REFLECTOR:
            return lazy_pgettext('telescope_type', 'Reflector')
        if self == TelescopeType.OTHER:
            return lazy_pgettext('telescope_type', 'Other')
        return ''


class Telescope(db.Model):
    __tablename__ = 'telescopes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    descr = db.Column(db.Text)
    telescope_type = db.Column(sqlalchemy.Enum(TelescopeType))
    aperture_mm = db.Column(db.Integer)
    focal_length_mm = db.Column(db.Integer)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class Eyepiece(db.Model):
    __tablename__ = 'eyepieces'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    descr = db.Column(db.Text)
    focal_length_mm = db.Column(db.Float, nullable=False)
    fov_deg = db.Column(db.Integer, nullable=False)
    diameter_inch = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class FilterType(FormEnum):
    UHC = 'UHC'
    OIII = 'OIII'
    CLS = 'CLS'
    HBETA = 'HBETA'
    OTHER = 'OTHER'

    def loc_text(self):
        if self == FilterType.UHC:
            return lazy_pgettext('filter_type', 'UHC')
        if self == FilterType.OIII:
            return lazy_pgettext('filter_type', 'OIII')
        if self == FilterType.CLS:
            return lazy_pgettext('filter_type', 'CLS')
        if self == FilterType.HBETA:
            return lazy_pgettext('filter_type', 'H-Beta')
        if self == FilterType.OTHER:
            return lazy_pgettext('filter_type', 'Other')
        return ''


class Filter(db.Model):
    __tablename__ = 'filters'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    descr = db.Column(db.Text)
    filter_type = db.Column(sqlalchemy.Enum(FilterType))
    diameter_inch = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
