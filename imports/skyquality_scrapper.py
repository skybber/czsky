#!/usr/bin/python

import requests
from bs4 import BeautifulSoup

url = 'http://www.skyquality.cz/location/show?locationId='

loc_id = 1

while True:
    r = requests.get(url + str(loc_id))

    soup = BeautifulSoup(r.content, 'html.parser')

    if (soup.find(text='Stránka nenalezena')):
        print('Finished')

    print('-------- Scrapping location:' + str(loc_id))
    name = soup.select_one('.location__title').text.strip()
    create_by = soup.find(text='Vytvořil/a').find_next().text.strip()
    coords = soup.find(text='Souřadnice').find_next().text.strip()
    elevation = soup.find(text='Nadm. výška').find_next().text.strip()
    descr = soup.find(text='Popis').find_next().text.strip()
    accessibility = soup.find(text='Přístupnost').find_next().text.strip()
    sqm_avg = soup.find(text='SQM průměr').find_next().text.strip()
    bortle_scale = soup.find(text='Bortle průměr').find_next().text.strip()

    indx = name.find(' — detail lokality')
    if indx >= 0:
        name = name[:indx]
    coords = coords[coords.index('(') + 1:coords.index(')')]

    print('Name:' + name)
    print('Created by:' + create_by)
    print('Coordinaktions:' + coords)
    print('Elevation:' + elevation)
    print('Descr:' + descr)
    print('Accessibility:' + accessibility)
    print('SQM avg:' + sqm_avg)
    print('Bortle:' + bortle_scale)

    loc_id += 1
