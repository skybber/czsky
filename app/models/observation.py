from enum import Enum
import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext
from flask import url_for

from .. import db

from app.commons.observation_utils import astro_text_to_html
from app.commons.form_utils import FormEnum


class Seeing(FormEnum):
        TERRIBLE = 'TERRIBLE'
        VERYBAD = 'VERYBAD'
        BAD = 'BAD'
        AVERAGE = 'AVERAGE'
        GOOD = 'GOOD'
        EXCELLENT = 'EXCELENT'

        def loc_text(self):
            if self == Seeing.TERRIBLE:
                return lazy_pgettext('seeing', 'Terrible')
            if self == Seeing.VERYBAD:
                return lazy_pgettext('seeing', 'Very bad')
            if self == Seeing.BAD:
                return lazy_pgettext('seeing', 'Bad')
            if self == Seeing.AVERAGE:
                return lazy_pgettext('seeing', 'Average')
            if self == Seeing.GOOD:
                return lazy_pgettext('seeing', 'Good')
            if self == Seeing.EXCELLENT:
                return lazy_pgettext('seeing', 'Excellent')
            return ''


class Transparency(FormEnum):
        UNUSUAL = 'UNUSUAL'
        VERYBAD = 'VERYBAD'
        BAD = 'BAD'
        AVERAGE = 'AVERAGE'
        GOOD = 'GOOD'
        EXCELLENT = 'EXCELENT'

        def loc_text(self):
            if self == Transparency.UNUSUAL:
                return lazy_pgettext('transparency', 'Unusual')
            if self == Transparency.VERYBAD:
                return lazy_pgettext('transparency', 'Very bad')
            if self == Transparency.BAD:
                return lazy_pgettext('transparency', 'Bad')
            if self == Transparency.AVERAGE:
                return lazy_pgettext('transparency', 'Average')
            if self == Transparency.GOOD:
                return lazy_pgettext('transparency', 'Good')
            if self == Transparency.EXCELLENT:
                return lazy_pgettext('transparency', 'Excellent')
            return ''


class ObservingSession(db.Model):
    __tablename__ = 'observing_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    title = db.Column(db.String(256), index=True)
    date_from = db.Column(db.DateTime, default=datetime.now(), index=True)
    date_to = db.Column(db.DateTime, default=datetime.now(), index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), index=True)
    location = db.relationship("Location")
    location_position = db.Column(db.String(256))
    sqm = db.Column(db.Float)
    faintest_star = db.Column(db.Float)
    seeing = db.Column(sqlalchemy.Enum(Seeing))
    transparency = db.Column(sqlalchemy.Enum(Transparency))
    weather = db.Column(db.Text)
    equipment = db.Column(db.Text)
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sqm_records = db.relationship('SqmFullRecord', backref='observing_session', cascade="all, delete-orphan", lazy=True)
    observations = db.relationship('Observation', backref='observing_session', cascade="all, delete-orphan", lazy=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    is_finished = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=False, index=True)

    def rating_to_int(self, m):
        if not self.rating:
            return 0
        return int(round(self.rating * m / 10))

    def loc_seeing(self):
        return self.seeing.loc_text() if self.seeing else ''

    def loc_transparency(self):
        return self.transparency.loc_text() if self.transparency else ''

    def find_observation_by_dso_id(self, dso_id):
        for o in self.observations:
            if o.target_type == ObservationTargetType.DSO:
                for oi_dso in o.deepsky_objects:
                    if oi_dso.id == dso_id:
                        return o
        return None

    def find_observation_by_double_star_id(self, double_star_id):
        for o in self.observations:
            if o.target_type == ObservationTargetType.DBL_STAR and o.double_star_id == double_star_id:
                return o
        return None

    def find_observation_by_comet_id(self, comet_id):
        for o in self.observations:
            if o.target_type == ObservationTargetType.COMET and o.comet_id == comet_id:
                return o
        return None

    def find_observation_by_planet_id(self, planet_id):
        for o in self.observations:
            if o.target_type == ObservationTargetType.PLANET and o.planet_id == planet_id:
                return o
        return None

    def find_observation_by_minor_planet_id(self, minor_planet_id):
        for o in self.observations:
            if o.target_type == ObservationTargetType.M_PLANET and o.minor_planet_id == minor_planet_id:
                return o
        return None


dso_observation_association_table = db.Table('observation_dsos', db.Model.metadata,
                                             db.Column('observation_id', db.Integer, db.ForeignKey('observations.id')),
                                             db.Column('dso_id', db.Integer, db.ForeignKey('deepsky_objects.id')),
                                             db.UniqueConstraint('observation_id', 'dso_id', name='unique_observation_dso'),
                                             )


class ObservationTargetType(Enum):
    DSO = 'DSO'
    DBL_STAR = 'DBL_STAR'
    COMET = 'COMET'
    M_PLANET = 'M_PLANET'
    PLANET = 'PLANET'


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship("User", foreign_keys=[user_id, ])
    observing_session_id = db.Column(db.Integer, db.ForeignKey('observing_sessions.id'), nullable=True, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), index=True)
    location = db.relationship("Location")
    location_position = db.Column(db.String(256))
    date_from = db.Column(db.DateTime, default=datetime.now(), index=True)
    date_to = db.Column(db.DateTime, default=datetime.now())
    sqm = db.Column(db.Float)
    faintest_star = db.Column(db.Float)
    seeing = db.Column(sqlalchemy.Enum(Seeing))
    telescope_id = db.Column(db.Integer, db.ForeignKey('telescopes.id'))
    telescope = db.relationship("Telescope")
    eyepiece_id = db.Column(db.Integer, db.ForeignKey('eyepieces.id'))
    eyepiece = db.relationship("Eyepiece")
    filter_id = db.Column(db.Integer, db.ForeignKey('filters.id'))
    filter = db.relationship("Filter")
    lens_id = db.Column(db.Integer, db.ForeignKey('lenses.id'))
    lens = db.relationship("Lens")
    accessories = db.Column(db.String(128))
    magnification = db.Column(db.Float)
    target_type = db.Column(sqlalchemy.Enum(ObservationTargetType))
    deepsky_objects = db.relationship("DeepskyObject", secondary=dso_observation_association_table)
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    double_star = db.relationship("DoubleStar")
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True)
    comet = db.relationship("Comet")
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), nullable=True)
    minor_planet = db.relationship("MinorPlanet")
    planet_id = db.Column(db.Integer, db.ForeignKey('planets.id'), nullable=True)
    planet = db.relationship("Planet")
    ra = db.Column(db.Float, index=True)
    dec = db.Column(db.Float, index=True)
    notes = db.Column(db.Text)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_ra(self):
        if self.target_type == ObservationTargetType.DSO:
            return self.deepsky_objects[0].ra if len(self.deepsky_objects) > 0 else None
        if self.target_type == ObservationTargetType.DBL_STAR:
            return self.double_star.ra_first
        return None

    def get_dec(self):
        if self.target_type == ObservationTargetType.DSO:
            return self.deepsky_objects[0].dec if len(self.deepsky_objects) > 0 else None
        if self.target_type == ObservationTargetType.DBL_STAR:
            return self.double_star.dec_first
        return None

    def get_target_name(self):
        if self.target_type == ObservationTargetType.DBL_STAR and self.double_star:
            return self.double_star.get_common_norm_name()
        if self.target_type == ObservationTargetType.PLANET and self.planet:
            return self.planet.get_localized_name()
        if self.target_type == ObservationTargetType.COMET and self.comet:
            return self.comet.designation
        if self.target_type == ObservationTargetType.M_PLANET and self.minor_planet:
            return self.minor_planet.designation
        if self.target_type == ObservationTargetType.DSO and self.deepsky_objects:
            return ','.join(dso.name for dso in self.deepsky_objects)
        return ''

    def get_observer_name(self):
        return self.user.full_name

    def get_location_id(self):
        if self.location_id is not None:
            return self.location_id
        if self.observing_session is not None:
            return self.observing_session.location_id
        return None

    def get_location(self):
        if self.location:
            return self.location
        if self.observing_session:
            return self.observing_session.location
        return None

    def get_location_position(self):
        if self.location_position:
            return self.location_position
        if self.observing_session:
            return self.observing_session.location_position
        return None

    def get_sqm(self):
        if self.sqm:
            return self.sqm
        if self.observing_session and self.observing_session.sqm:
            return self.observing_session.sqm
        return None

    def get_seeing(self):
        if self.seeing:
            return self.seeing
        if self.observing_session and self.observing_session.seeing:
            return self.observing_session.seeing
        return None

    def loc_seeing(self):
        seeing = self.get_seeing()
        return seeing.loc_text() if seeing else ''

    def targets_from_observation_to_html(self):
        return self._targets_to_html('stobservation', self.id)

    def targets_from_session_to_html(self):
        return self._targets_to_html('observation', self.observing_session_id)

    def _targets_to_html(self, back, back_id):
        if self.target_type == ObservationTargetType.DBL_STAR and self.double_star:
            return '<a class="sw-link" href="' + url_for('main_double_star.double_star_seltab', double_star_id=self.double_star_id, back=back, back_id=back_id) + '">' + self.double_star.get_common_name() + '</a>'
        if self.target_type == ObservationTargetType.PLANET and self.planet:
            return '<a href="' + url_for('main_planet.planet_info', planet_iau_code=self.planet.iau_code, back=back, back_id=back_id) + '">' + self.planet.get_localized_name() + '</a>'
        if self.target_type == ObservationTargetType.COMET and self.comet:
            return '<a class="sw-link" href="' + url_for('main_comet.comet_seltab', comet_id=self.comet.comet_id, back=back, back_id=back_id) + '">' + self.comet.designation + '</a>'
        if self.target_type == ObservationTargetType.M_PLANET and self.minor_planet:
            return '<a href="' + url_for('main_minor_planet.minor_planet_info', minor_planet_id=self.minor_planet.int_designation, back=back, back_id=back_id) + '">' + self.minor_planet.designation + '</a>'
        formatted_dsos = []
        for dso in self.deepsky_objects:
            formatted_dsos.append('<a class="sw-link" href="' + url_for('main_deepskyobject.deepskyobject_seltab', dso_id=dso.name, back=back, back_id=back_id) + '">' + dso.denormalized_name() + '</a>')
        return ','.join(formatted_dsos)

    def notes_to_html(self):
        return astro_text_to_html(self.observing_session_id, self.notes)


class ObsSessionPlanRun(db.Model):
    __tablename__ = 'obs_session_plan_runs'
    id = db.Column(db.Integer, primary_key=True)
    observing_session_id = db.Column(db.Integer, db.ForeignKey('observing_sessions.id'), nullable=False, index=True)
    session_plan_id = db.Column(db.Integer, db.ForeignKey('session_plans.id'), nullable=False)
    observing_session = db.relationship("ObservingSession")
    session_plan = db.relationship("SessionPlan")
