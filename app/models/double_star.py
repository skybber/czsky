from datetime import datetime

from .. import db

from skyfield.units import Angle
from app.commons.coordinates import ra_to_str_short, dec_to_str_short, ra_to_str, dec_to_str
from .constellation import Constellation


class DoubleStar(db.Model):
    __tablename__ = 'double_stars'
    id = db.Column(db.Integer, primary_key=True)
    wds_number = db.Column(db.String(10), index=True)
    common_cat_id = db.Column(db.String(20), index=True)
    components = db.Column(db.String(12))
    other_designation = db.Column(db.Text)
    pos_angle = db.Column(db.Integer)
    separation = db.Column(db.Float)
    mag_first = db.Column(db.Float)
    mag_second = db.Column(db.Float)
    delta_mag = db.Column(db.Float)
    spectral_type = db.Column(db.String(20))
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    constellation = db.relationship("Constellation")
    ra_first = db.Column(db.Float)
    dec_first = db.Column(db.Float)

    def ra_first_str_short(self):
        return ra_to_str_short(self.ra_first)

    def dec_first_str_short(self):
        return dec_to_str_short(self.dec_first)

    def ra_second_str_short(self):
        return ra_to_str_short(self.ra_second)

    def dec_second_str_short(self):
        return dec_to_str_short(self.dec_second)

    def ra_first_str(self):
        return ra_to_str(self.ra_first)

    def dec_first_str(self):
        return dec_to_str(self.dec_first)

    def get_constellation_iau_code(self):
        if self.constellation_id:
            return Constellation.get_id_dict().get(self.constellation_id).iau_code
        return ''
