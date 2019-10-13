from datetime import datetime

from .. import db

class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now(), index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), index=True)
    rating = db.Column(db.Integer)
    omd_content = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sql_readings = db.relationship('SqlReading', backref='observation', lazy=True)
    observation_items = db.relationship('ObservationItem', backref='observation', lazy=True)

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

class ObservationItem(db.Model):
    __tablename__ = 'observation_items'
    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'))
    deep_sky_object_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'))
    date_time = db.Column(db.DateTime, nullable=False)
    omd_notes = db.Column(db.Text)
