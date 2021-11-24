import sqlalchemy
from datetime import datetime
from flask_babel import lazy_pgettext
from enum import Enum

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


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    title = db.Column(db.String(256), index=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now(), index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), index=True)
    location = db.relationship("Location")
    location_position = db.Column(db.String(256))
    sqm = db.Column(db.Float)
    seeing = db.Column(sqlalchemy.Enum(Seeing))
    transparency = db.Column(sqlalchemy.Enum(Transparency))
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)
    omd_content = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sqm_records = db.relationship('SqmFullRecord', backref='observation', lazy=True)
    observation_items = db.relationship('ObservationItem', backref='observation', lazy=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    def rating_to_int(self, m):
        if not self.rating:
            return 0
        return int(round(self.rating * m / 10))

    def get_prev_next_item(self, dso_id):
        observation_list = sorted(self.observation_items, key=lambda x: x.id)
        prev_dso = None
        next_dso = None
        find_next = False
        for item in observation_list:
            for dso in item.deepsky_objects:
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


dso_observation_item_association_table = db.Table('observation_item_dsos', db.Model.metadata,
    db.Column('observation_item_id', db.Integer, db.ForeignKey('observation_items.id')),
    db.Column('dso_id', db.Integer, db.ForeignKey('deepsky_objects.id'))
)


class ObservationItem(db.Model):
    __tablename__ = 'observation_items'
    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    txt_deepsky_objects = db.Column(db.Text)
    header_notes = db.Column(db.Text)
    notes = db.Column(db.Text)
    deepsky_objects = db.relationship("DeepskyObject", secondary=dso_observation_item_association_table)

    def deepsky_objects_to_html(self):
        return deepsky_objects_to_html(self.observation_id, self.deepsky_objects)

    def header_notes_to_html(self):
        return astro_text_to_html(self.observation_id, self.header_notes)


class ObservationPlanRun(db.Model):
    __tablename__ = 'observation_plan_runs'
    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'), nullable=False)
    session_plan_id = db.Column(db.Integer, db.ForeignKey('session_plans.id'), nullable=False)
    session_plan = db.relationship("SessionPlan")
    observation = db.relationship("Observation")
