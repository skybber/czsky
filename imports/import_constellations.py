import csv

from app import db
from app.models.constellation import Constellation

def import_constellations(data_file):
    """Initialize constellation table."""
    from sqlalchemy.exc import IntegrityError

    with open(data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            c = Constellation(
                iau_code = row['IAU code'],
                name = row['Latin name / Nom latin '],
                descr = '',
                image = row['Image']
                )
            db.session.add(c)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()