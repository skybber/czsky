from datetime import datetime
import requests
from sqlalchemy.exc import IntegrityError
from astroquery.simbad import Simbad

from flask import (
    current_app,
)

from app import db

from app.models.deepskyobject import DeepskyObject, UserDsoDescription, UserDsoApertureDescription
from app.models.user import User

def import_wikipedia_ngc(do_update=False):

    simbad = Simbad()
    simbad.add_votable_fields('otype')

    user_wikipedia = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA')).first()
    user_editor_cs = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_CS')).first()

    if not user_wikipedia:
        print('User editor.wikipedia not found!')
        return

    try:
        for i in range(1, 7841):
            dso_name = 'NGC{}'.format(i)
            czsky_name = dso_name

            dso = DeepskyObject.query.filter_by(name=dso_name).first()

            if not dso:
                dso = DeepskyObject.query.filter_by(name=dso_name + 'A').first()
                if dso:
                    czsky_name = czsky_name + 'A'

            if not dso:
                dso = DeepskyObject.query.filter_by(name=dso_name + '_1').first()
                if dso:
                    czsky_name = czsky_name + '_1'

            if dso and dso.master_id:
                dso = DeepskyObject.query.filter_by(id=dso.master_id).first()

            try:
                resp = requests.get('https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&explaintext=1&titles=NGC%20{}'.format(i))
            except ConnectionError:
                continue
            if resp.status_code != 200:
                continue
            data = resp.json()

            found = False
            if 'query' in data and 'pages' in data['query']:
                pages = data['query']['pages']
                for page_id, page_data in pages.items():
                    if 'extract' in page_data:
                        extract = page_data['extract'].strip()
                        if extract:
                            parts = extract.split('\n\n\n')
                            if len(parts) >= 1:
                                dso_descr = parts[0].strip()

                                found = True

                                if not dso:
                                    print('{} not exist. {}'.format(dso_name, dso_descr), flush=True)
                                    break

                                mag8_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_editor_cs.id).first()

                                udd = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_wikipedia.id, lang_code='en').first()

                                if udd and not do_update:
                                    continue

                                if udd:
                                    print('Updating data {}'.format(dso_name))
                                    udd.text = dso_descr
                                    udd.update_by = user_wikipedia.id
                                    udd.update_date = datetime.now()
                                else:
                                    print('Inserting data {}'.format(dso_name))
                                    udd = UserDsoDescription(
                                        dso_id=dso.id,
                                        user_id=user_wikipedia.id,
                                        rating=mag8_descr.rating if mag8_descr else 0,
                                        lang_code='en',
                                        cons_order=mag8_descr.cons_order if mag8_descr else 100000,
                                        text=dso_descr,
                                        references=None,
                                        common_name=dso.common_name,
                                        create_by=user_wikipedia.id,
                                        update_by=user_wikipedia.id,
                                        create_date=datetime.now(),
                                        update_date=datetime.now(),

                                    )
                                db.session.add(udd)
                                db.session.flush()
                                db.session.commit()
            if dso and not found:
                print('{} not found on wiki. czsky_name={}'.format(dso_name, czsky_name), flush=True)
        db.session.flush()
        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
