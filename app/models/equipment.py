import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext

from .. import db

from app.commons.form_utils import FormEnum


class TelescopeType(FormEnum):
    NAKED_EYE = 'NAKED_EYE'
    BINOCULAR = 'BINOCULAR'
    NEWTON = 'NEWTON'
    REFRACTOR = 'REFRACTOR'
    CASSEGRAIN = 'CASSEGR'
    SCHMIDT_CASSEGRAIN = 'S_CASSEG'
    MAKSUTOV = 'MAKSUTOV'
    KUTTER = 'KUTTER'
    OTHER = 'OTHER'

    @classmethod
    def choices_without_naked_eye(cls):
        return [(choice, choice.loc_text()) for choice in cls if choice != TelescopeType.NAKED_EYE]

    def loc_text(self):
        if self == TelescopeType.BINOCULAR:
            return lazy_pgettext('telescope_type', 'Binocular')
        if self == TelescopeType.NEWTON:
            return lazy_pgettext('telescope_type', 'Newton')
        if self == TelescopeType.REFRACTOR:
            return lazy_pgettext('telescope_type', 'Refractor')
        if self == TelescopeType.CASSEGRAIN:
            return lazy_pgettext('telescope_type', 'Cassegrain')
        if self == TelescopeType.SCHMIDT_CASSEGRAIN:
            return lazy_pgettext('telescope_type', 'Schmidt-Cassegrain')
        if self == TelescopeType.MAKSUTOV:
            return lazy_pgettext('telescope_type', 'Maksutov')
        if self == TelescopeType.KUTTER:
            return lazy_pgettext('telescope_type', 'Kutter')
        if self == TelescopeType.OTHER:
            return lazy_pgettext('telescope_type', 'Other')
        return ''


class Telescope(db.Model):
    __tablename__ = 'telescopes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    model = db.Column(db.String(128))
    vendor = db.Column(db.String(128))
    descr = db.Column(db.Text)
    telescope_type = db.Column(sqlalchemy.Enum(TelescopeType))
    aperture_mm = db.Column(db.Integer)
    focal_length_mm = db.Column(db.Integer)
    fixed_magnification = db.Column(db.Float)
    light_grasp = db.Column(db.Float)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_fov(self, eyepiece):
        if self.focal_length_mm and \
                eyepiece.focal_length_mm and \
                eyepiece.focal_length_mm > 0 and \
                eyepiece.fov_deg:
            return eyepiece.fov_deg / (self.focal_length_mm / eyepiece.focal_length_mm)
        return None


class Eyepiece(db.Model):
    __tablename__ = 'eyepieces'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    model = db.Column(db.String(128))
    vendor = db.Column(db.String(128))
    descr = db.Column(db.Text)
    focal_length_mm = db.Column(db.Float)
    fov_deg = db.Column(db.Integer)
    diameter_inch = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class FilterType(FormEnum):
    UHC = 'UHC'
    OIII = 'OIII'
    CLS = 'CLS'
    HBETA = 'HBETA'
    HALPHA = 'HALPHA'
    COLOR = 'COLOR'
    NEUTRAL = 'NEUTRAL'
    CORRECTIVE = 'CORRECTIVE'
    SOLAR = 'SOLAR'
    BROAD_BAND = 'BROAD_BAND'
    NARROW_BAND = 'NARROW_BAND'
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
        if self == FilterType.HALPHA:
            return lazy_pgettext('filter_type', 'H-Alpha')
        if self == FilterType.COLOR:
            return lazy_pgettext('filter_type', 'Color')
        if self == FilterType.NEUTRAL:
            return lazy_pgettext('filter_type', 'Neutral')
        if self == FilterType.CORRECTIVE:
            return lazy_pgettext('filter_type', 'Corrective')
        if self == FilterType.SOLAR:
            return lazy_pgettext('filter_type', 'Solar')
        if self == FilterType.BROAD_BAND:
            return lazy_pgettext('filter_type', 'Broad Band')
        if self == FilterType.NARROW_BAND:
            return lazy_pgettext('filter_type', 'Narrow Band')
        if self == FilterType.OTHER:
            return lazy_pgettext('filter_type', 'Other')
        return ''


class Filter(db.Model):
    __tablename__ = 'filters'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    model = db.Column(db.String(128), index=True)
    vendor = db.Column(db.String(128), index=True)
    descr = db.Column(db.Text)
    filter_type = db.Column(sqlalchemy.Enum(FilterType))
    diameter_inch = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class LensType(FormEnum):
    BARLOW = 'BARLOW'
    COMA_CORRECTOR = 'COMA_CORR'
    OTHER = 'OTHER'

    def loc_text(self):
        if self == LensType.BARLOW:
            return lazy_pgettext('lens_type', 'Barlow')
        if self == LensType.COMA_CORRECTOR:
            return lazy_pgettext('lens_type', 'Coma Corrector')
        if self == FilterType.OTHER:
            return LensType('filter_type', 'Other')
        return ''


class Lens(db.Model):
    __tablename__ = 'lenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    model = db.Column(db.String(128))
    vendor = db.Column(db.String(128))
    descr = db.Column(db.Text)
    lens_type = db.Column(sqlalchemy.Enum(LensType))
    magnification = db.Column(db.Float)
    diameter_inch = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
