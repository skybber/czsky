from flask_babel import gettext
from skyfield.api import load

all_planets = None

class Planet:
    def __init__(self, name, body_key, eph):
        self.name = name
        self.eph = eph[body_key]

    def localized_name(self):
        return gettext(self.name)


def get_all_planets():
    global all_planets
    if all_planets is None:
        eph = load('de421.bsp')
        all_planets = [
            Planet('mercury', 'MERCURY', eph),
            Planet('venus', 'VENUS', eph),
            Planet('mars', 'MARS', eph),
            Planet('jupiter', 'JUPITER_BARYCENTER', eph),
            Planet('saturn', 'SATURN_BARYCENTER', eph),
            Planet('uranus', 'URANUS_BARYCENTER', eph),
            Planet('neptune', 'NEPTUNE_BARYCENTER', eph),
            Planet('pluto', 'PLUTO_BARYCENTER', eph),
        ]
    return all_planets
