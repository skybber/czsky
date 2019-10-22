from datetime import datetime

from .. import db

from .deepskyobject import DeepskyObject

class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    title = db.Column(db.String(256), index=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now(), index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), index=True)
    txt_location_name = db.Column(db.String(128), nullable=False, index=True)
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)
    omd_content = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sql_readings = db.relationship('SqlReading', backref='observation', lazy=True)
    observation_items = db.relationship('ObservationItem', backref='observation', lazy=True)

    def rating_to_int(self, m):
        if not self.rating:
            return 0
        return int(round(self.rating * m / 10))

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
