from datetime import datetime

from .. import db

DB_UPDATE_COMETS_COBS_KEY = 'COMETS_COBS'
DB_UPDATE_COMETS_BRIGHT_KEY = 'COMETS_BRIGHT'
DB_UPDATE_COMETS_POS_KEY = 'COMETS_POS'
DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY = 'MINOR_PLANETS_POS_BRIGHT'


class DbUpdate(db.Model):
    __tablename__ = 'db_updates'
    id = db.Column(db.String(50), primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    expired = db.Column(db.DateTime)
