from .. import db

AU_KM = 149597870.7
LUNAR_DISTANCE_KM = 384400.0
# Below this distance Earth perturbs the orbit noticeably; Keplerian positions are only approximate.
NEO_IMPRECISE_DIST_AU = 0.01


class NeoCloseApproach(db.Model):
    """Close approach of a near-Earth asteroid to Earth, from the JPL CNEOS close-approach API."""
    __tablename__ = 'neo_close_approaches'
    id = db.Column(db.Integer, primary_key=True)
    # Null when the object is not (yet) in MPC NEA.txt, e.g. discovered days before the approach.
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), index=True)
    designation = db.Column(db.String(30), nullable=False, index=True)
    approach_time = db.Column(db.DateTime, nullable=False, index=True)  # UTC
    dist_au = db.Column(db.Float, nullable=False)
    dist_min_au = db.Column(db.Float)
    dist_max_au = db.Column(db.Float)
    v_rel_kms = db.Column(db.Float)
    h = db.Column(db.Float)
    t_sigma = db.Column(db.String(16))
    orbit_id = db.Column(db.String(16))
    est_peak_mag = db.Column(db.Float)

    minor_planet = db.relationship('MinorPlanet', lazy='joined')

    def dist_ld(self):
        return self.dist_au * AU_KM / LUNAR_DISTANCE_KM
