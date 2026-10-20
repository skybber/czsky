import numpy as np

from .. import db


class NeoEphemerisSegment(db.Model):
    """
    Regular table of geocentric state vectors of a near-Earth asteroid from JPL Horizons
    (ICRF, TDB, au and au/day), interpolated with cubic Hermite polynomials. An asteroid can
    have several segments: a coarse one and finer ones around a close approach; the finest
    covering segment wins.
    """
    __tablename__ = 'neo_ephemeris_segments'
    id = db.Column(db.Integer, primary_key=True)
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), nullable=False, index=True)
    start_jd = db.Column(db.Float, nullable=False)  # TDB
    step_minutes = db.Column(db.Float, nullable=False)
    count = db.Column(db.Integer, nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)  # little-endian float64, count x 6
    # Interpolation checked against Horizons wherever this is the finest covering segment.
    verified = db.Column(db.Boolean, nullable=False, default=False)
    max_check_error_arcsec = db.Column(db.Float)
    orbit_solution = db.Column(db.String(32))  # e.g. 'JPL#75'
    revision = db.Column(db.String(16), nullable=False)
    fetched_at = db.Column(db.DateTime, nullable=False)  # UTC

    @property
    def end_jd(self):
        return self.start_jd + (self.count - 1) * self.step_minutes / 1440.0

    def states(self):
        return np.frombuffer(self.data, dtype='<f8').reshape(self.count, 6)
