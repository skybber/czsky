from datetime import datetime

from .. import db

from skyfield.units import Angle


class Supernova(db.Model):
    __tablename__ = 'supernovas'
    id = db.Column(db.Integer, primary_key=True)
    designation = db.Column(db.String(50), index=True)
    host_galaxy = db.Column(db.String(30))
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    constellation = db.relationship("Constellation")
    sn_type = db.Column(db.String(30))
    z = db.Column(db.Float)
    ra = db.Column(db.Float)
    dec = db.Column(db.Float)
    offset = db.Column(db.String(30))
    max_mag = db.Column(db.Float)
    max_mag_date = db.Column(db.DateTime)
    latest_mag = db.Column(db.Float)
    latest_observed = db.Column(db.DateTime)
    first_observed = db.Column(db.DateTime)
    discoverer = db.Column(db.String(100))
    aka = db.Column(db.String(100))
    is_archived = db.Column(db.Boolean, default=False, nullable=False)

    def ra_str(self):
        if self.ra:
            return '%02d:%02d:%04.1f' % Angle(radians=self.ra).hms(warn=False)
        return 'nan'

    def dec_str(self):
        if self.ra:
            sgn, d, m, s = Angle(radians=self.dec).signed_dms(warn=False)
            sign = '-' if sgn < 0.0 else '+'
            return '%s%02d:%02d:%04.1f' % (sign, d, m, s)
        return 'nan'

    def ra_str_short(self):
        if self.ra:
            return '%02d:%02d:%02d' % Angle(radians=self.ra).hms(warn=False)
        return 'nan'

    def dec_str_short(self):
        if self.ra:
            sgn, d, m, s = Angle(radians=self.dec).signed_dms(warn=False)
            sign = '-' if sgn < 0.0 else '+'
            return '%s%02d:%02d:%02d' % (sign, d, m, s)
        return 'nan'

    def get_constellation_iau_code(self):
        if self.constellation:
            return self.constellation.iau_code
        return ''
