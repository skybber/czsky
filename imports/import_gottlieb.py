from datetime import datetime
import re

from os import listdir
from os.path import isfile, join

from sqlalchemy.exc import IntegrityError

from app import db

from app.models.deepskyobject import DeepskyObject, UserDsoDescription, UserDsoApertureDescription
from app.models.user import User

GOTTLIEB_REF = 'Notes by [Steve Gottlieb](https://www.astronomy-mall.com/Adventures.In.Deep.Space/steve.ngc.htm)'

def _found_dso(dso_name, dso_descr, dso_apert_descr, user_gottlieb, user_8mag):
    dso = DeepskyObject.query.filter_by(name=dso_name).first()

    if dso and dso.master_id:
        dso = DeepskyObject.query.filter_by(id=dso.master_id).first()

    if dso:
        mag8_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_8mag.id).first()

        # update constellation ID since it is missing in vic catalogue

        print('Importing {}'.format(dso_name))

        udd = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_gottlieb.id, lang_code='en').first()
        if udd:
            udd.text = dso_descr
            udd.references = GOTTLIEB_REF
            udd.update_by = user_gottlieb.id
            udd.update_date = datetime.now()
        else:
            udd = UserDsoDescription(
                dso_id = dso.id,
                user_id = user_gottlieb.id,
                rating = mag8_descr.rating if mag8_descr else 0,
                lang_code = 'en',
                cons_order = mag8_descr.cons_order if mag8_descr else 100000,
                text = dso_descr,
                references = GOTTLIEB_REF,
                common_name = dso.common_name,
                create_by = user_gottlieb.id,
                update_by = user_gottlieb.id,
                create_date = datetime.now(),
                update_date = datetime.now(),

            )
        db.session.add(udd)

        for apert, apert_descr in dso_apert_descr.items():
            if apert == 'Naked-eye':
                apert_class = 'Naked-eye'
            else:
                apertf = float(apert)
                if apertf < 8:
                    apert_class = '100/150'
                elif apertf < 12:
                    apert_class = '200/250'
                elif apertf < 16:
                    apert_class = '300/350'
                elif apertf < 24:
                    apert_class = '400/500'
                elif apertf < 36:
                    apert_class = '600/800'
                else:
                    apert_class = '900/1200'

            uad = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=user_gottlieb.id, aperture_class=apert_class, lang_code='en').first()

            if uad:
                uad.text = apert_descr
                uad.update_by = user_gottlieb.id
                uad.update_date = datetime.now()
            else:
                uad = UserDsoApertureDescription(
                    dso_id = dso.id,
                    user_id = user_gottlieb.id,
                    lang_code = 'en',
                    aperture_class = apert_class,
                    text = apert_descr,
                    is_public = True,
                    create_by = user_gottlieb.id,
                    update_by = user_gottlieb.id,
                    create_date = datetime.now(),
                    update_date = datetime.now(),
                )

            db.session.add(uad)
        db.session.flush()


def import_gottlieb(gottlieb_dir):

    user_gottlieb = User.query.filter_by(user_name='s.gottlieb').first()
    user_8mag = User.query.filter_by(user_name='8mag').first()

    gottlieb_files = [f for f in listdir(gottlieb_dir) if isfile(join(gottlieb_dir, f))]

    try:

        for filename in gottlieb_files:
            file = open(join(gottlieb_dir,filename), 'r')
            lines   = file.readlines()

            i = 0

            search_obj_id = True

            dso_name = None
            dso_apert_descr = {}
            dso_descr = ''
            last_apert = None
            ignored_text = True

            while i < len(lines):
                line = lines[i]
                i += 1

                if len(line.strip()) == 0:
                    continue

                if line.strip() == '******************************':
                    if dso_name:
                        _found_dso(dso_name, dso_descr, dso_apert_descr, user_gottlieb, user_8mag)
                    search_obj_id = True
                    dso_name = None
                    dso_descr = ''
                    dso_apert_descr = {}
                    last_apert = None
                    ignored_text = True
                    continue

                if search_obj_id:
                    pobj_id = re.match(r'(NGC|IC)\s*(\d+).*', line)
                    if pobj_id:
                        search_obj_id = False
                        dso_name = pobj_id.group(1) + pobj_id.group(2)
                    continue

                papertd = re.match(r'((?:\d+(?:\.\d+)?")|(?:Naked-eye))\:?(.*)', line)
                if papertd:
                    if last_apert:
                        if dso_descr:
                            dso_apert_descr[last_apert] = dso_apert_descr[last_apert] + '\n\n' + dso_descr
                            dso_descr = ''
                    last_apert = papertd.group(1)
                    apert_prefix = ''
                    if last_apert != 'Naked-eye':
                        last_apert = last_apert[:-1]
                        apert_prefix = papertd.group(1) + ' '
                    if last_apert in dso_apert_descr:
                        dso_apert_descr[last_apert] = dso_apert_descr[last_apert] + '\n\n' + apert_prefix + papertd.group(2)
                    else:
                        dso_apert_descr[last_apert] = apert_prefix + papertd.group(2)
                    ignored_text = False
                    continue

                if ignored_text:
                    continue

                if len(dso_descr) > 0:
                    dso_descr += '\n'

                dso_descr += line

        if dso_name:
            _found_dso(dso_name, dso_descr, dso_apert_descr, user_gottlieb, user_8mag)

        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
