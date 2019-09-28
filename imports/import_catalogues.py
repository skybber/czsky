import csv

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.catalogue import Catalogue

def import_catalogues(data_file):
    """Initialize catagues table."""

    with open(data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            c = Catalogue(
                code = row['code'],
                name = row['name'],
                descr = row['description'],
                )
            db.session.add(c)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()