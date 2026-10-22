import csv

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.catalogue import Catalogue


def import_catalogues(data_file):
    """Initialize catagues table."""

    with open(data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            for row in reader:
                # id is stable, code, name and description may change
                c = Catalogue.query.filter_by(id=int(row['id'])).first()
                if c is None:
                    c = Catalogue(id=int(row['id']))
                c.code = row['code']
                c.name = row['name']
                c.descr = row['description']
                db.session.add(c)
            db.session.commit()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()