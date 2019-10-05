import requests
from datetime import datetime
from bs4 import BeautifulSoup
import sqlite3

from app import db
from app.models.user import User
from app.models.location import Location
from sqlalchemy.exc import IntegrityError
from lat_lon_parser import parse as lonlat_parse

url = 'http://www.skyquality.cz/location/show?locationId='

SKYQ_ORIGIN_ID_PREFIX = 'skyq_'

class SkyQualityLocation(object):
    def __init__(self, **kwargs):
        valid_keys = ["location_id", "name", "create_by", "coords", "elevation", "descr", "accessibility", "sqm_avg", "bortle_scale"]
        for key in valid_keys:
            setattr(self, key, kwargs.get(key))

def scrap_sq_location(skyquality_location_id):
        r = requests.get(url + str(skyquality_location_id))

        soup = BeautifulSoup(r.content, 'html.parser')

        if (soup.find(text='Stránka nenalezena')):
            return None

        print('-------- Scrapping location:' + str(skyquality_location_id))

        name = soup.select_one('.location__title').text.strip()
        indx = name.find(' — detail lokality')
        if indx >= 0:
            name = name[:indx]

        coords = soup.find(text='Souřadnice').find_next().text.strip()
        coords = coords[coords.index('(') + 1:coords.index(')')]

        bortle_scale = soup.find(text='Bortle průměr').find_next().text.strip()

        if '(' in bortle_scale:
            bortle_scale = bortle_scale[:bortle_scale.index('(')].strip()

        sqm_avg = soup.find(text='SQM průměr').find_next().text.strip()

        if '(' in sqm_avg:
            sqm_avg = sqm_avg[:sqm_avg.index('(')].strip()

        descr = soup.find(text='Popis').find_next().text.strip()
        if descr == 'NULL':
            descr = ''

        sq_location = SkyQualityLocation(location_id = skyquality_location_id,
                                        name = name,
                                        coords = coords,
                                        create_by = soup.find(text='Vytvořil/a').find_next().text.strip(),
                                        elevation = soup.find(text='Nadm. výška').find_next().text.strip(),
                                        descr = descr,
                                        accessibility = soup.find(text='Přístupnost').find_next().text.strip(),
                                        sqm_avg = sqm_avg,
                                        bortle_scale = bortle_scale,
                                      )
        print('Name:' + sq_location.name)
        print('Created by:' + sq_location.create_by)
        print('Coordinaktions:' + sq_location.coords)
        print('Elevation:' + sq_location.elevation)
        print('Descr:' + sq_location.descr)
        print('Accessibility:' + sq_location.accessibility)
        print('SQM avg:' + sq_location.sqm_avg)
        print('Bortle:' + sq_location.bortle_scale)

        return sq_location

def convert_sqlocation2location(sq_location, user_skyquality):
        try:
            bortle = float(sq_location.bortle_scale)
            rating = round(10 - (bortle - 1))
        except ValueError:
            bortle = None
            rating = 5

        longitude = None
        latitude = None

        if sq_location.coords:
            longLat = sq_location.coords.split(',')
            if longLat and len(longLat) == 2:
                try:
                    longitude = lonlat_parse(longLat[0])
                    latitude = lonlat_parse(longLat[1])
                except ValueError:
                    print('Unknown long-lat format=' + sq_location.coords)
                    return None

        is_for_observation = not any(x in sq_location.accessibility for x in ['nevhodné', 'nepřístupné'])

        loc = Location(
            name = sq_location.name,
            longitude = longitude,
            latitude = latitude,
            descr = sq_location.descr,
            bortle = bortle,
            rating = rating,
            #  sql_readings = db.relationship('SqlReading', backref='location', lazy=True)
            country_code = 'CZ',
            user_id = None,
            is_public = True,
            is_for_observation = is_for_observation,
            origin_id = SKYQ_ORIGIN_ID_PREFIX + str(sq_location.location_id),
            create_by = user_skyquality.id,
            update_by = user_skyquality.id,
            create_date = datetime.now(),
            update_date = datetime.now(),
        )

        return loc


def save_location(loc):
    if loc:
        db.session.add(loc)
        try:
            db.session.commit()
        except IntegrityError as e:
            print('Commit failed:', e)
            db.session.rollback()


def do_import_skyquality_locations(skyquality_db_name, delete_old):

    user_skyquality = User.query.filter_by(email='skyquality').first()

    if not user_skyquality:
        print('User skyquality not found.')
        return

    db_connection = None
    try:
        db_connection = sqlite3.connect(skyquality_db_name)
    except Exception:
        print('Connection to db="' + skyquality_db_name + '" failed.')
        return

    cur = db_connection.cursor()
    if delete_old:
        cur.execute('delete from locations')
        db_connection.commit()
        Location.query.filter(Location.origin_id.like(SKYQ_ORIGIN_ID_PREFIX +'%')).delete(synchronize_session=False)
        try:
            db.session.commit()
        except IntegrityError as e:
            print('Commit failed:', e)
            db.session.rollback()
    else:
        added_locations = 0
        for row_sqloc in cur.execute("SELECT location_id,name,coords,create_by,elevation,descr,accessibility,sqm_avg,bortle_scale FROM locations").fetchall():
            sq_location = SkyQualityLocation(location_id = row_sqloc[0],
                                            name = row_sqloc[1],
                                            coords = row_sqloc[2],
                                            create_by = row_sqloc[3],
                                            elevation = row_sqloc[4],
                                            descr = row_sqloc[5],
                                            accessibility = row_sqloc[6],
                                            sqm_avg = row_sqloc[7],
                                            bortle_scale = row_sqloc[8],
                                            )
            location = Location.query.filter_by(id=sq_location.location_id).first()
            if not location:
                loc = convert_sqlocation2location(sq_location, user_skyquality)
                save_location(loc)
                added_locations += 1
        print(str() + ' previously scrapped locations are put to DB.')

    max_loc = cur.execute("SELECT max(location_id) FROM locations").fetchone()
    skyquality_location_id = max_loc[0] + 1 if max_loc[0] else 1

    while True:
        sq_location = scrap_sq_location(skyquality_location_id)

        if sq_location is None:
            print('SkyQuality location_id=' + str(skyquality_location_id) + ' does not exist.')
            print('Import finished.')
            return

        loc = convert_sqlocation2location(sq_location, user_skyquality)

        save_location(loc)

        cur.execute("INSERT INTO locations (location_id, name, coords, create_by, elevation, descr, accessibility, sqm_avg, bortle_scale) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            sq_location.location_id,
            sq_location.name,
            sq_location.coords,
            sq_location.create_by,
            sq_location.elevation,
            sq_location.descr,
            sq_location.accessibility,
            sq_location.sqm_avg,
            sq_location.bortle_scale
            ))

        db_connection.commit()

        skyquality_location_id += 1
