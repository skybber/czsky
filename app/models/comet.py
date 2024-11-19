from .. import db

from app.commons.coordinates import ra_to_str_short, dec_to_str_short, ra_to_str, dec_to_str

from . import Constellation


class Comet(db.Model):
    __tablename__ = 'comets'
    id = db.Column(db.Integer, primary_key=True)
    comet_id = db.Column(db.String(50), index=True)
    designation = db.Column(db.String(50))
    number = db.Column(db.Float)
    orbit_type = db.Column(db.String(2))
    designation_packed = db.Column(db.String(30))
    perihelion_year = db.Column(db.Integer)
    perihelion_month = db.Column(db.Integer)
    perihelion_day = db.Column(db.Float)
    perihelion_distance_au = db.Column(db.Float)
    eccentricity = db.Column(db.Float)
    argument_of_perihelion_degrees = db.Column(db.Float)
    longitude_of_ascending_node_degrees = db.Column(db.Float)
    inclination_degrees = db.Column(db.Float)
    perturbed_epoch_year = db.Column(db.Float)
    perturbed_epoch_month = db.Column(db.Float)
    perturbed_epoch_day = db.Column(db.Float)
    magnitude_g = db.Column(db.Float)
    magnitude_k = db.Column(db.Float)
    reference = db.Column(db.String(30))
    mag = db.Column(db.Float)
    eval_mag = db.Column(db.Float)
    real_mag = db.Column(db.Float)
    real_coma_diameter = db.Column(db.Float)
    cur_ra = db.Column(db.Float)
    cur_dec = db.Column(db.Float)
    cur_constell_id = db.Column(db.Integer, db.ForeignKey('constellations.id'), index=True)
    is_disintegrated = db.Column(db.Boolean, default=False)

    def cur_ra_str(self):
        return ra_to_str(self.cur_ra) if self.cur_ra is not None else ''

    def cur_dec_str(self):
        return dec_to_str(self.cur_dec) if self.cur_dec is not None else ''

    def cur_ra_str_short(self):
        return ra_to_str_short(self.cur_ra) if self.cur_ra is not None else ''

    def cur_dec_str_short(self):
        return dec_to_str_short(self.cur_dec) if self.cur_dec is not None else ''

    def cur_constell(self):
        return Constellation.get_constellation_by_id(self.cur_constell_id) if self.cur_constell_id is not None else None


class CometObservation(db.Model):
    __tablename__ = 'comet_observations'
    id = db.Column(db.Integer, primary_key=True)
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True, index=True)
    date = db.Column(db.DateTime, index=True)
    mag = db.Column(db.Float)
    coma_diameter = db.Column(db.Float)
    notes = db.Column(db.Text)