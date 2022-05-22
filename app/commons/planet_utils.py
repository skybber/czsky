from flask_babel import gettext
from skyfield.api import load

all_planets = None

class Planet:
    def __init__(self, name, body_key, eph):
        self.name = name
        self.eph = eph[body_key]


def get_all_planets():
    global all_planets
    if all_planets is None:
        eph = load('de421.bsp')
        all_planets = [
            Planet(gettext('mercury'), 'MERCURY', eph),
            Planet(gettext('venus'), 'VENUS', eph),
            Planet(gettext('mars'), 'MARS', eph),
            Planet(gettext('jupiter'), 'JUPITER_BARYCENTER', eph),
            Planet(gettext('saturn'), 'SATURN_BARYCENTER', eph),
            Planet(gettext('uranus'), 'URANUS_BARYCENTER', eph),
            Planet(gettext('neptune'), 'NEPTUNE_BARYCENTER', eph),
            Planet(gettext('pluto'), 'PLUTO_BARYCENTER', eph),
        ]
    return all_planets
