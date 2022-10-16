from sqlalchemy.exc import IntegrityError

from app import db
from app.models.planet import Planet

PLANET_DEFS = [
    ['mercury', 1],
    ['venus', 2],
    ['mars', 4],
    ['jupiter', 5],
    ['saturn', 6],
    ['uranus', 7],
    ['neptune', 8],
    ['pluto', 9]
]


def import_db_planets():
    """Initialize planet table."""
    for pld in PLANET_DEFS:
        pl = Planet.query.filter_by(int_designation=pld[1]).first()
        if not pl:
            pl = Planet()
            pl.int_designation = pld[1]
            pl.iau_code = pld[0]
            db.session.add(pl)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
