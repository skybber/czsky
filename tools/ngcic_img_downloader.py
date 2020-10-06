#!/usr/bin/python
import urllib
import urllib3
import math
from bs4 import BeautifulSoup

url='http://objekty.astro.cz/'

http = urllib3.PoolManager()

for id in range(1,7840):
    response = http.request('GET', url + 'ngc' + str(id))
    soup = BeautifulSoup(response.data)
    imgs = soup.findAll("img")
    for img in imgs:
        src = img['src']
        if '/obr/objekty/ngc/' in src:
            print('Downloading {} ..'.format(src))
            urllib.request.urlretrieve(url+src, 'NGC' + ('0' * (4 - int(math.log10(id) + 1))) + str(id) + '.jpg')
