from .. import db


class MinorPlanet(db.Model):
    __tablename__ = 'minor_planets'
    id = db.Column(db.Integer, primary_key=True)
    int_designation = db.Column(db.Integer, index=True)
    magnitude_H = db.Column(db.Float)
    magnitude_G = db.Column(db.Float)
    epoch = db.Column(db.String(6))
    mean_anomaly_degrees = db.Column(db.Float)
    argument_of_perihelion_degrees = db.Column(db.Float)
    longitude_of_ascending_node_degrees = db.Column(db.Float)
    inclination_degrees = db.Column(db.Float)
    eccentricity = db.Column(db.Float)
    mean_daily_motion_degrees = db.Column(db.Float)
    semimajor_axis_au = db.Column(db.Float)
    uncertainty = db.Column(db.String(6))
    reference = db.Column(db.String(10))
    observations = db.Column(db.Integer)
    oppositions = db.Column(db.Integer)
    observation_period = db.Column(db.String(9))
    rms_residual_arcseconds = db.Column(db.Float)
    coarse_perturbers = db.Column(db.String(4))
    precise_perturbers = db.Column(db.String(4))
    computer_name = db.Column(db.String(11))
    hex_flags = db.Column(db.String(5))
    designation = db.Column(db.String(30))
    last_observation_date = db.Column(db.String(9))

