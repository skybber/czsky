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


class SkyQualityLocation(object):
    def __init__(self, **kwargs):
        valid_keys = ["name", "create_by", "coords", "elevation", "descr", "accessibility", "sqm_avg", "bortle_scale"]
        for key in valid_keys:
            setattr(self, key, kwargs.get(key))

def scrapLocation(skyquality_location_id):
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

        location = SkyQualityLocation(name = name,
                                      coords = coords,
                                      create_by = soup.find(text='Vytvořil/a').find_next().text.strip(),
                                      elevation = soup.find(text='Nadm. výška').find_next().text.strip(),
                                      descr = descr,
                                      accessibility = soup.find(text='Přístupnost').find_next().text.strip(),
                                      sqm_avg = sqm_avg,
                                      bortle_scale = bortle_scale,
                                      )

        print('Name:' + location.name)
        print('Created by:' + location.create_by)
        print('Coordinaktions:' + location.coords)
        print('Elevation:' + location.elevation)
        print('Descr:' + location.descr)
        print('Accessibility:' + location.accessibility)
        print('SQM avg:' + location.sqm_avg)
        print('Bortle:' + location.bortle_scale)

        return location


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
        cur.execute('delete from locations;')
        db_connection.commit()
        Location.query.filter_by(create_by=user_skyquality.id).delete()


    sqlqry = "SELECT max(location_id) FROM locations;"
    c = cur.execute(sqlqry)
    c = c.fetchone();
    skyquality_location_id = c[0] + 1 if c[0] else 1

    while True:
        skyQualityLocation = scrapLocation(skyquality_location_id)

        if skyQualityLocation is None:
            print('SkyQuality location_id=' + str(skyquality_location_id) + ' does not exist.')
            print('Import finished.')
            return

        try:
            bortle = float(skyQualityLocation.bortle_scale)
            rating = round(10 - (bortle - 1))
        except ValueError:
            bortle = None
            rating = 5

        longitude = None
        latitude = None

        if skyQualityLocation.coords:
            longLat = skyQualityLocation.coords.split(',')
            if longLat and len(longLat) == 2:
                try:
                    longitude = lonlat_parse(longLat[0])
                    latitude = lonlat_parse(longLat[1])
                except ValueError:
                    print('Unknown long-lat format=' + skyQualityLocation.coords)


        loc = Location(
            name = skyQualityLocation.name,
            longitude = longitude,
            latitude = latitude,
            descr = skyQualityLocation.descr,
            bortle = bortle,
            rating = rating,
            #  sql_readings = db.relationship('SqlReading', backref='location', lazy=True)
            country_code = 'CZ',
            user_id = None,
            is_public = True,
            create_by = user_skyquality.id,
            update_by = user_skyquality.id,
            create_date = datetime.now(),
            update_date = datetime.now(),
        )

        db.session.add(loc)
        try:
            db.session.commit()
        except IntegrityError as e:
            print('Commit failed:', e)
            db.session.rollback()

        cur.execute("INSERT INTO locations (location_id, name, coords, elevation, descr, accessibility, sqm_avg, bortle_scale) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
            skyquality_location_id,
            skyQualityLocation.name,
            skyQualityLocation.coords,
            skyQualityLocation.elevation,
            skyQualityLocation.descr,
            skyQualityLocation.accessibility,
            skyQualityLocation.sqm_avg,
            skyQualityLocation.bortle_scale
            ))

        db_connection.commit()

        skyquality_location_id += 1

