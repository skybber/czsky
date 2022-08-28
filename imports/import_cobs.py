import requests
from bs4 import BeautifulSoup


def scrap_cobs():
    r = requests.get('https://cobs.si/cobs/recent/')

    soup = BeautifulSoup(r.content, 'html.parser')

    all_comets_text = soup.select('.text-info')

    for comet_text in all_comets_text:
        parts = comet_text.select('strong')
        year_observs = comet_text.select('code')
        if parts and year_observs:
            comet_name = parts[0].select_one('a')
            if comet_name:
                print('{}'.format(comet_name.text))
            for i in range(1, len(parts)):
                year = parts[i].text
                if (i - 1) < len(year_observs):
                    yo = year_observs[i-1]
                    if year and yo:
                        print('{}'.format(year))
                        observs = ' '.join(yo.decode_contents().split()).split('<br/>')
                        for o in observs:
                            if o.startswith('&nbsp&nbsp&nbsp'):
                                print('----{}'.format(o))
                            else:
                                print('{}'.format(o))
