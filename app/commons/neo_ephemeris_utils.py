"""Storing and loading Horizons ephemeris segments of near-Earth asteroids."""
import hashlib
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import numpy as np

from app import db
from app.models import NeoEphemerisSegment
from app.commons.horizons_utils import EphemerisSegment

# Segments whose coverage ended this long ago are deleted.
NEO_EPHEMERIS_ENDED_RETENTION = timedelta(days=2)
# Segments not refreshed for this long (the asteroid left the list) are deleted.
NEO_EPHEMERIS_STALE_RETENTION = timedelta(days=30)
_LOADED_CACHE_SIZE = 256

_loaded = OrderedDict()  # (minor_planet_id, revision) -> segments


def datetime_to_jd(dt):
    """Julian date of a naive UTC datetime (UTC scale; enough for retention checks)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return 2440587.5 + (dt - datetime(1970, 1, 1)).total_seconds() / 86400.0


def segment_to_row(minor_planet_id, segment, fetched_at):
    states = np.ascontiguousarray(segment.states, dtype='<f8')
    return NeoEphemerisSegment(
        minor_planet_id=minor_planet_id,
        start_jd=segment.start_jd,
        step_minutes=segment.step_minutes,
        count=len(states),
        data=states.tobytes(),
        verified=bool(segment.verified),
        max_check_error_arcsec=segment.max_check_error_arcsec,
        orbit_solution=(segment.orbit_solution or '')[:32],
        revision=segment.revision(),
        fetched_at=fetched_at,
    )


def row_to_segment(row):
    return EphemerisSegment(start_jd=row.start_jd, step_minutes=row.step_minutes, states=row.states().copy(),
                            verified=row.verified, max_check_error_arcsec=row.max_check_error_arcsec,
                            orbit_solution=row.orbit_solution or '')


def replace_neo_ephemeris(minor_planet_id, segments, fetched_at):
    """Replaces all segments of the asteroid in the current transaction; the caller commits."""
    NeoEphemerisSegment.query.filter_by(minor_planet_id=minor_planet_id).delete(synchronize_session=False)
    db.session.add_all([segment_to_row(minor_planet_id, segment, fetched_at) for segment in segments])


def neo_ephemeris_revision(minor_planet_id):
    """Revision of the stored ephemeris of the asteroid ('' without one): one cheap query."""
    revisions = sorted(r for (r,) in db.session.query(NeoEphemerisSegment.revision)
                       .filter(NeoEphemerisSegment.minor_planet_id == minor_planet_id))
    if not revisions:
        return ''
    return hashlib.sha1('|'.join(revisions).encode()).hexdigest()[:16]


def load_neo_ephemeris(minor_planet_id):
    """
    (segments, revision) of the asteroid, one consistent version: the revision is read first,
    the segments are loaded once per revision and kept in the process. ([], '') without data.
    """
    revision = neo_ephemeris_revision(minor_planet_id)
    if not revision:
        return [], ''
    key = (minor_planet_id, revision)
    segments = _loaded.get(key)
    if segments is None:
        rows = NeoEphemerisSegment.query.filter_by(minor_planet_id=minor_planet_id).all()
        segments = [row_to_segment(row) for row in rows]
        if neo_ephemeris_revision(minor_planet_id) != revision:
            # Replaced between the two reads: do not cache a mix, use what was read.
            return segments, neo_ephemeris_revision(minor_planet_id)
        _loaded[key] = segments
        while len(_loaded) > _LOADED_CACHE_SIZE:
            _loaded.popitem(last=False)
    else:
        _loaded.move_to_end(key)
    return segments, revision


def delete_obsolete_neo_ephemeris_query(now):
    """Query of segments whose coverage ended or that were not refreshed for a long time."""
    ended_before_jd = datetime_to_jd(now - NEO_EPHEMERIS_ENDED_RETENTION)
    end_jd = NeoEphemerisSegment.start_jd + (NeoEphemerisSegment.count - 1) * NeoEphemerisSegment.step_minutes / 1440.0
    return NeoEphemerisSegment.query.filter(
        (end_jd < ended_before_jd) | (NeoEphemerisSegment.fetched_at < now - NEO_EPHEMERIS_STALE_RETENTION))
