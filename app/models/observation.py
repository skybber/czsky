from .. import db
from datetime import datetime

class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    ranking = db.Column(db.Integer)
    notes = db.Column(db.Text)
    # sql_readings = db.relationship('SqlReading', backref='observation', lazy=True)
    observation_items = db.relationship('ObservationItem', backref='observation', lazy=True)

class ObservationItem(db.Model):
    __tablename__ = 'observation_items'
    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'))
    deep_sky_object_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'))
    date = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text)
