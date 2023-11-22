from datetime import datetime

from .. import db

DB_UPDATE_COMETS = 'COMETS_UPDATE'
DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY = 'MINOR_PLANETS_POS_BRIGHT'
DB_UPDATE_SUPERNOVAE = 'SUPERNOVAE_UPDATE'
DB_DELETE_SUPERNOVAE = 'SUPERNOVAE_DELETE'


class DbUpdate(db.Model):
    __tablename__ = 'db_updates'
    id = db.Column(db.String(50), primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    expired = db.Column(db.DateTime)
