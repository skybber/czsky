from datetime import datetime

from .. import db
from LatLon23 import LatLon

from app.commons.coordinates import *

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    descr = db.Column(db.Text)
    bortle = db.Column(db.Float)
    rating = db.Column(db.Integer)
    # sql_readings = db.relationship('SqmReading', backref='location', lazy=True)
    country_code = db.Column(db.String(2))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_public = db.Column(db.Boolean)
    is_for_observation = db.Column(db.Boolean)
    origin_id = db.Column(db.String(32), index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

    def coordinates(self):
        pos = LatLon(self.longitude, self.latitude)
        return str(latlon_to_string(pos))

    def full_coordinates(self):
        pos = LatLon(self.longitude, self.latitude)
        return str(latlon_to_string(pos)) + '(' + str(self.longitude) + ',' + str(self.latitude) + ')'

    def url_mapy_cz(self):
        return mapy_cz_url(self.longitude, self.latitude)

    def url_google_maps(self):
        return google_url(self.longitude, self.latitude)

    def url_open_street_map(self):
        return open_street_map_url(self.longitude, self.latitude)

user_to_location_links = db.Table('user_to_location_links',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)
