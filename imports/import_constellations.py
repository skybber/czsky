import csv

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.constellation import Constellation


def import_constellations(data_file):
    """Initialize constellation table."""

    with open(data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            full_season = row["Observation Season / Saison d'observation"]
            if 'Winter' in full_season:
                season = 'winter'
            elif 'Spring' in full_season:
                season = 'spring'
            elif 'Summer' in full_season:
                season = 'summer'
            elif 'Autumn' in full_season:
                season = 'autumn'
            elif 'Southern' in full_season:
                season = 'southern'
            c = Constellation.query.filter_by(iau_code=row['IAU code']).first()
            if not c:
                c = Constellation()
            c.iau_code = row['IAU code']
            c.name = row['Latin name / Nom latin '].lower()
            c.season = season
            c.descr = ''
            c.image = row['Image']
            db.session.add(c)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
