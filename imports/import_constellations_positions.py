import numpy as np

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.constellation import Constellation


def import_constellations_positions(filename):
    sf = open(filename, 'r')
    lines = sf.readlines()
    sf.close()

    print('Importing constellations positions...')

    try:
        for line in lines:
            ra = float(line[0:6].strip())
            dec = float(line[8:15].strip())
            iau_code = line[17:20]
            constellation = Constellation.query.filter_by(iau_code=iau_code).first()
            constellation.label_ra = ra / 12 * np.pi
            constellation.label_dec = dec / 180 * np.pi
            db.session.add(constellation)

        db.session.commit()

    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
