import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext
from flask import url_for

from .. import db

from app.commons.observation_utils import deepsky_objects_to_html, astro_text_to_html
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

    def rating_to_int(self, m):
        if not self.rating:
            return 0
        return int(round(self.rating * m / 10))

    def get_prev_next_item(self, dso_id):
        observation_list = sorted(self.observations, key=lambda x: x.id)
        prev_dso = None
        next_dso = None
        find_next = False
        for observation in observation_list:
            for dso in observation.deepsky_objects:
                if dso.id == dso_id:
                    find_next = True
                elif not find_next:
                    prev_dso = dso
                else:
                    next_dso = dso
                    return prev_dso, next_dso
        return prev_dso, next_dso

    def loc_seeing(self):
        return self.seeing.loc_text() if self.seeing else ''

    def loc_transparency(self):
        return self.transparency.loc_text() if self.transparency else ''


dso_observation_association_table = db.Table('observation_dsos', db.Model.metadata,
                                             db.Column('observation_id', db.Integer, db.ForeignKey('observations.id')),
                                             db.Column('dso_id', db.Integer, db.ForeignKey('deepsky_objects.id'))
                                             )


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship("User", foreign_keys=[user_id,])
    observing_session_id = db.Column(db.Integer, db.ForeignKey('observing_sessions.id'), nullable=True)
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
    notes = db.Column(db.Text)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    deepsky_objects = db.relationship("DeepskyObject", secondary=dso_observation_association_table)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_target_name(self):
        if self.deepsky_objects:
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

    def deepsky_objects_from_observation_to_html(self):
        return self._deepsky_objects_from_session_to_html('stobservation', self.id)

    def deepsky_objects_from_session_to_html(self):
        return self._deepsky_objects_from_session_to_html('observation', self.observing_session_id)

    def _deepsky_objects_from_session_to_html(self, back, back_id):
        formatted_dsos = []
        for dso in self.deepsky_objects:
            formatted_dsos.append('<a href="' + url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back=back, back_id=back_id) + '">' + dso.denormalized_name() + '</a>')
        return ','.join(formatted_dsos)

    def notes_to_html(self):
        return astro_text_to_html(self.observing_session_id, self.notes)


class ObsSessionPlanRun(db.Model):
    __tablename__ = 'obs_session_plan_runs'
    id = db.Column(db.Integer, primary_key=True)
    observing_session_id = db.Column(db.Integer, db.ForeignKey('observing_sessions.id'), nullable=False)
    session_plan_id = db.Column(db.Integer, db.ForeignKey('session_plans.id'), nullable=False)
    observing_session = db.relationship("ObservingSession")
    session_plan = db.relationship("SessionPlan")
