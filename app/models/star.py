from datetime import datetime

from .. import db

from skyfield.units import Angle

class Star(db.Model):
    __tablename__ = 'stars'
    id = db.Column(db.Integer, primary_key=True)
    hr = db.Column(db.Integer, unique=True, index=True)                     # Harvard Revised Number = Bright Star Number
    bayer_flamsteed = db.Column(db.String(10), index=True)                  # Name, generally Bayer and/or Flamsteed name
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    constellation = db.relationship("Constellation")
    hd = db.Column(db.Integer, unique=True, index=True)                     # Henry Draper Catalog Number
    sao = db.Column(db.Integer, index=True)                                 # SAO Catalog Number
    fk5 = db.Column(db.Integer, unique=True, index=True)
    multiple = db.Column(db.String(1))                                      # Double or multiple-star code
    ads = db.Column(db.String(5))                                           # Aitken's Double Star Catalog (ADS) designation
    ads_comp = db.Column(db.String(2))                                      # ADS number components
    var_id = db.Column(db.String(9))                                        # Variable star identification
    ra = db.Column(db.Float)
    dec = db.Column(db.Float)
    mag = db.Column(db.Float)                                               # Visual magnitude code
    bv = db.Column(db.Float)                                                # B-V color in the UBV system
    sp_type = db.Column(db.String(20))                                      # Spectral type
    dmag = db.Column(db.Float)                                              # Magnitude difference of double, or brightest multiple
    sep = db.Column(db.Float)                                               # Separation of components in Dmag if occultation binary.
    mult_id = db.Column(db.String(4))                                       # Identifications of components in Dmag
    mult_cnt = db.Column(db.Integer)                                        # Number of components assigned to a multiple

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


class UserStarDescription(db.Model):
    __tablename__ = 'user_star_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'), nullable=False)
    constellation = db.relationship("Constellation")
    common_name = db.Column(db.String(256), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lang_code = db.Column(db.String(2))
    text = db.Column(db.Text)
    star_id = db.Column(db.Integer, db.ForeignKey('stars.id'))
    star = db.relationship("Star")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
