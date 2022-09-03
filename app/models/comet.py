from datetime import datetime

from .. import db


class Comet(db.Model):
    __tablename__ = 'comets'
    id = db.Column(db.Integer, primary_key=True)
    comet_id = db.Column(db.String(50))
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
    eval_mag = db.Column(db.Float)


class CometObservation(db.Model):
    __tablename__ = 'comet_observations'
    id = db.Column(db.Integer, primary_key=True)
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True, index=True)
    date = db.Column(db.DateTime, index=True)
    mag = db.Column(db.Float)
    coma_diameter = db.Column(db.Float)
    notes = db.Column(db.Text)