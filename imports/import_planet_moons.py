from sqlalchemy.exc import IntegrityError

from app import db
from app.models.planet_moon import PlanetMoon
from app.models.planet import Planet

PLANET_MOONS_DEFS = [
    ['Mars', 'Phobos', 401],
    ['Mars', 'Deimos', 402],

    ['Jupiter', 'Io', 501],
    ['Jupiter', 'Europa', 502],
    ['Jupiter', 'Ganymede', 503],
    ['Jupiter', 'Callisto', 504],
    ['Jupiter', 'Amalthea', 505],
    ['Jupiter', 'Himalia', 506],

    ['Saturn', 'Titan', 601],
    ['Saturn', 'Rhea', 602],
    ['Saturn', 'Iapetus', 603],
    ['Saturn', 'Enceladus', 604],
    ['Saturn', 'Mimas', 605],
    ['Saturn', 'Tethys', 606],
    ['Saturn', 'Dione', 607],
    ['Saturn', 'Phoebe', 608],
    ['Saturn', 'Hyperion', 609],

    ['Uranus', 'Titania', 701],
    ['Uranus', 'Oberon', 702],
    ['Uranus', 'Umbriel', 703],
    ['Uranus', 'Ariel', 704],
    ['Uranus', 'Miranda', 705],

    ['Neptune', 'Triton', 801],
]


def import_db_planet_moons():
    """Initialize planet moons table."""
    for pld in PLANET_MOONS_DEFS:
        pl_moon = PlanetMoon.query.filter_by(name=pld[1]).first()
        if not pl_moon:
            pl_moon = PlanetMoon()
            pl_moon.iau_number = pld[2]
            pl_moon.name = pld[1]
            pl_moon.planet_id = Planet.get_by_iau_code(pld[0].lower()).id
            db.session.add(pl_moon)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
