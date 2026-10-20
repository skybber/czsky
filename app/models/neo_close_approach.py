import math

from .. import db

AU_KM = 149597870.7
LUNAR_DISTANCE_KM = 384400.0
# Below this distance Earth perturbs the orbit noticeably; Keplerian positions are only approximate.
NEO_IMPRECISE_DIST_AU = 0.01
# Diameter from H: D = 1329 km / sqrt(albedo) * 10^(-H/5). Albedo is mostly unknown;
# the range covers bright (0.25) to dark (0.05) surfaces.
NEO_ALBEDO_RANGE = (0.25, 0.05)


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
    # Rough H + 5 log10(delta) at closest approach, no phase; used to preselect approaches
    # and shown only when the orbit is not available.
    est_peak_mag = db.Column(db.Float)
    # Brightest apparent magnitude around the approach, computed from the MPC orbit with phase angle.
    peak_mag = db.Column(db.Float)
    peak_time = db.Column(db.DateTime)  # UTC

    minor_planet = db.relationship('MinorPlanet', lazy='joined')

    def best_peak_mag(self):
        return self.peak_mag if self.peak_mag is not None else self.est_peak_mag

    def abs_magnitude(self):
        """H from MPC like the brightness computation; CAD H for asteroids without an orbit."""
        if self.minor_planet is not None and self.minor_planet.magnitude_H is not None:
            return self.minor_planet.magnitude_H
        return self.h

    def diameter_range_km(self):
        h = self.abs_magnitude()
        if h is None:
            return None
        return tuple(1329.0 / math.sqrt(albedo) * 10.0 ** (-h / 5.0) for albedo in NEO_ALBEDO_RANGE)

    def diameter_range_str(self):
        """E.g. '20-45 m' or '1.1-2.4 km' (2 significant digits, one unit for both ends)."""
        diameters = self.diameter_range_km()
        if diameters is None:
            return ''
        small, large = diameters
        if large < 1.0:
            return '{}–{} m'.format(_two_significant(small * 1000.0), _two_significant(large * 1000.0))
        return '{}–{} km'.format(_two_significant(small), _two_significant(large))

    def dist_ld(self):
        return self.dist_au * AU_KM / LUNAR_DISTANCE_KM


def _two_significant(value):
    if value <= 0:
        return '0'
    rounded = float('{:.2g}'.format(value))
    digits = max(1 - int(math.floor(math.log10(rounded))), 0)
    return '{:.{}f}'.format(rounded, digits)
