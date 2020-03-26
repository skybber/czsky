from datetime import datetime
from sqlalchemy import Index

from .. import db
from skyfield.units import Angle
from .catalogue import Catalogue

BROWSING_CATALOGS = ('M', 'Abell', 'SH2', 'VIC', 'NGC', 'HCG')

ALL_APERTURE_DESCRIPTIONS = ( '100/150', '200/250', '300/350', '400/450', '500/550', '110/660')

SHOWN_APERTURE_DESCRIPTIONS = ( '100/150', '200/250', '300/350', '400/450', '500/550' )

class SqmDevice(db.Model):
    __tablename__ = 'sqm_devices'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), index=True)
    type = db.Column(db.String(1))
    sub_type = db.Column(db.String(16))
    name = db.Column(db.String(32))
    descr = db.Column(db.Text)
    user_id = db.Column(db.String(16))

class SqmFullRecord(db.Model):
    __tablename__ = 'sqm_full_records'
    id = db.Column(db.Integer, primary_key=True)
    sqm_device_id = db.Column(db.Integer, db.ForeignKey('sqm_devices.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    observation_id = db.Column(db.Integer, db.ForeignKey('observations.id'))
    date = db.Column(db.DateTime)
    weather = db.Column(db.Text)
    notes = db.Column(db.Text)
    sqm_read_values = db.relationship('SqmFullRecordValue', backref='sqm_reading', lazy=True)

class SqmFullRecordValue(db.Model):
    __tablename__ = 'sqm_full_record_values'
    id = db.Column(db.Integer, primary_key=True)
    sqm_reading_id = db.Column(db.Integer, db.ForeignKey('sqm_full_records.id'), nullable=False)
    sky_position =  db.Column(db.Integer)
    value_1 = db.Column(db.Float)
    value_2 = db.Column(db.Float)
    value_3 = db.Column(db.Float)
    value_4 = db.Column(db.Float)
    value_5 = db.Column(db.Float)


class SqmRecord(db.Model):
    __bind_key__ = 'sqm_sql'
    __tablename__ = 'sqm_records'
    id = db.Column(db.Integer, primary_key=True)
    sqm_device_id = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Integer, nullable=False)           # SQM * 100
    date_time = db.Column(db.DateTime, nullable=False)

Index('sqm_record_index', SqmRecord.sqm_device_id, SqmRecord.date_time)
