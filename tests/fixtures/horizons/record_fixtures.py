"""
Records the JPL Horizons responses used by tests/test_horizons_utils.py (needs network).

    python tests/fixtures/horizons/record_fixtures.py

Vector tables are stored under the request key used by the tests' replay_fetch; observer
tables (astrometric ICRF RA/Dec, QUANTITIES=1) are the references for the coordinate contract
test. Re-recording replaces both, so they always belong to the same orbit solution.
"""
import hashlib
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

from app.commons import horizons_utils as hu  # noqa: E402

CASES = {
    # name: (command, start JD TDB, stop JD TDB, observer times JD TT between table nodes)
    '2016NV': ('DES=2016 NV;', 2461382.5, 2461384.5, [2461382.7201, 2461383.1337, 2461384.0119]),
    '2023BU': ('DES=2023 BU;', 2459971.0, 2459972.0, [2459971.5150, 2459971.5203, 2459971.5212, 2459971.5300]),
}
SITES = {
    # name: Horizons SITE_COORD 'E-lon,lat,alt km' or None for the geocenter
    'geocenter': None,
    'prague': '14.4,50.1,0.3',
    'chile': '-70.7,-30.2,2.2',
}
OBSERVER_SITES = {'2016NV': ['geocenter', 'prague', 'chile'], '2023BU': ['geocenter', 'chile']}


def fixture_key(command, start, stop, step):
    return hashlib.sha1('{}|{:.9f}|{:.9f}|{:g}'.format(command, start, stop, step).encode()).hexdigest()[:16]


def recording_fetch(command, start, stop, step):
    text = hu.request_vector_text(command, start, stop, step)
    with open(os.path.join(HERE, 'vectors_{}.txt'.format(fixture_key(command, start, stop, step))), 'w') as f:
        f.write(text)
    time.sleep(0.5)  # be gentle with Horizons
    return hu.parse_vector_table(text)


def record_observer(name, command, tlist, site):
    params = {
        'format': 'text', 'COMMAND': "'{}'".format(command), 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES',
        'EPHEM_TYPE': 'OBSERVER', 'TLIST_TYPE': 'JD', 'TIME_TYPE': 'TT',
        'TLIST': ' '.join("'{}'".format(jd) for jd in tlist),
        'QUANTITIES': "'1,20'", 'ANG_FORMAT': 'DEG', 'EXTRA_PREC': 'YES', 'CSV_FORMAT': 'YES',
    }
    if SITES[site] is None:
        params['CENTER'] = "'500@399'"
    else:
        params.update({'CENTER': "'coord@399'", 'COORD_TYPE': 'GEODETIC', 'SITE_COORD': "'{}'".format(SITES[site])})
    response = requests.get(hu.HORIZONS_API_URL, params=params, timeout=120)
    response.raise_for_status()
    with open(os.path.join(HERE, 'observer_{}_{}.txt'.format(name, site)), 'w') as f:
        f.write(response.text)
    time.sleep(0.5)


def main():
    for name, (command, start, stop, tlist) in CASES.items():
        segments = hu.build_verified_ephemeris(command, start, stop, fetch=recording_fetch)
        print(name, [(s.step_minutes, s.verified, round(s.max_check_error_arcsec, 4)) for s in segments])
        for site in OBSERVER_SITES[name]:
            record_observer(name, command, tlist, site)


if __name__ == '__main__':
    main()
