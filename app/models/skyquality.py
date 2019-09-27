from datetime import datetime

from .. import db

class SqlDevice(db.Model):
    __tablename__ = 'sql_devices'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(1))
    sub_type = db.Column(db.String(16))
    name = db.Column(db.String(32))
    descr = db.Column(db.Text)
    user_id = db.Column(db.String(16))

class SqlReading(db.Model):
    __tablename__ = 'sql_readings'
    id = db.Column(db.Integer, primary_key=True)
    sql_device_id = db.Column(db.Integer, db.ForeignKey('sql_devices.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'))
    date = db.Column(db.DateTime, nullable=False)
    wether = db.Column(db.Text)
    notes = db.Column(db.Text)
    sql_read_values = db.relationship('SqlReadValue', backref='sql_reading', lazy=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

class SqlReadValue(db.Model):
    __tablename__ = 'sql_read_values'
    id = db.Column(db.Integer, primary_key=True)
    sql_reading_id = db.Column(db.Integer, db.ForeignKey('sql_readings.id'), nullable=False)
    sky_position =  db.Column(db.Integer)
    value_1 = db.Column(db.Float)
    value_2 = db.Column(db.Float)
    value_3 = db.Column(db.Float)
    value_4 = db.Column(db.Float)
    value_5 = db.Column(db.Float)
