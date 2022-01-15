import csv

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.catalogue import Catalogue


def import_catalogues(data_file):
    """Initialize catagues table."""

    with open(data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            Catalogue.query.delete()
            db.session.commit()
            for row in reader:
                c = Catalogue(
                    id = row['id'],
                    code = row['code'],
                    name = row['name'],
                    descr = row['description'],
                    )
                db.session.add(c)
            db.session.commit()
        except IntegrityError:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()