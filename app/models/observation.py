from datetime import datetime
from flask_babel import gettext

from .. import db

from app.commons.observation_utils import deepsky_objects_to_html, astro_text_to_html

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
    seeing = db.Column(db.String(16))
    transparency = db.Column(db.String(16))
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)
    omd_content = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sqm_records = db.relationship('SqmFullRecord', backref='observation', lazy=True)
    observation_items = db.relationship('ObservationItem', backref='observation', lazy=True)
    is_public = db.Column(db.Boolean, default=False)

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
        return gettext(self.seeing) if self.seeing else ''

    def loc_transparency(self):
        return gettext(self.transparency) if self.seeing else ''

dso_observation_item_association_table = db.Table('observation_item_dsos', db.Model.metadata,
    db.Column('observation_item_id', db.Integer, db.ForeignKey('observation_items.id')),
    db.Column('dso_id', db.Integer, db.ForeignKey('deepsky_objects.id'))
)

class ObservationItem(db.Model):
    __tablename__ = 'observation_items'
    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'))
    date_time = db.Column(db.DateTime, nullable=False)
    txt_deepsky_objects = db.Column(db.Text)
    notes = db.Column(db.Text)
    deepsky_objects = db.relationship("DeepskyObject", secondary=dso_observation_item_association_table)

    def deepsky_objects_to_html(self):
        dso_list = self.txt_deepsky_objects.split(':')[0]
        return deepsky_objects_to_html(self.observation_id, dso_list)

    def notes_to_html(self):
        descr = self.txt_deepsky_objects.split(':')
        if len(descr) > 1 and descr[1]:
            text = descr[1]
        else:
            text = self.notes
        return astro_text_to_html(self.observation_id, text)
