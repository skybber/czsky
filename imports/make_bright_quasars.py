"""
Generates bright quasar data from the Veron-Cetty & Veron catalogue of quasars and active nuclei,
13th edition (VizieR VII/258):

  - data/supplements/Bright quasars, Veron-Cetty & Veron 13th.sup
      HNSKY supplement with new QSO objects. Used by the DB import and by the chart engine (fchart3).
  - data/dsolist/BrightQuasars.csv
      DSO list "Bright quasars".

Selection:
  - quasars and BL Lac objects brighter than V=15.0 with z >= 0.15
    (lower z objects are mostly nuclei of galaxies already present in the DSO catalogue)
  - distant quasars with z >= 2.5 brighter than V=16.5
  - well-known objects listed in FAMOUS_OBJECTS

Objects in EXISTING_DSOS are already in the DSO catalogue (HNSKY). They are not added to the supplement
and the DSO list refers to the existing objects.

Distance is the light-travel distance (lookback time) for Planck 2018 cosmology in light years.

Usage: python -m imports.make_bright_quasars
"""
import csv
import io
import urllib.parse
import urllib.request
from datetime import date

import numpy as np

VIZIER_URL = 'https://vizier.cds.unistra.fr/viz-bin/asu-tsv'
VIZIER_TABLE = 'VII/258/vv10'
VIZIER_COLUMNS = 'Name,RAJ2000,DEJ2000,Vmag,z,Cl,Sp'

SUPPLEMENT_FILE = 'data/supplements/Bright quasars, Veron-Cetty & Veron 13th.sup'
DSO_LIST_FILE = 'data/dsolist/BrightQuasars.csv'

BRIGHT_MAG_LIMIT = 15.0
BRIGHT_MIN_Z = 0.15
DISTANT_MAG_LIMIT = 16.5
DISTANT_MIN_Z = 2.5

# Planck 2018 flat LambdaCDM (radiation neglected)
H0 = 67.66
OMEGA_M = 0.30966
HUBBLE_TIME_GYR = 977.792 / H0

# Veron-Cetty & Veron name -> common name used in czsky (None = derived from catalogue name)
FAMOUS_OBJECTS = {
    '3C 48.0': None,
    'S5 0014+81': None,
    'OJ 287': None,
    'Q 0957+561A': 'Twin Quasar A',
    'Q 0957+561B': 'Twin Quasar B',
    'MARK 421': None,
    '3C 249.1': None,
    'B2 1225+31': 'Ton 618',
    '3C 279': None,
    '3C 345.0': None,
    'MARK 501': None,
    'PKS 2155-304': None,
    'BL LAC': 'BL Lacertae',
    'Q 2237+0305': 'Einstein Cross',
    '3C 454.3': None,
}

# Veron-Cetty & Veron name -> DSO already present in czsky catalogue
EXISTING_DSOS = {
    '3C 273.0': 'PGC41121',
    'MARK 421': 'UGC6132',
    'MARK 501': 'UGC10599',
}


def _fetch_vizier(constraints):
    params = [('-source', VIZIER_TABLE), ('-out', VIZIER_COLUMNS), ('-out.max', '10000')] + constraints
    url = VIZIER_URL + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as resp:
        content = resp.read().decode('utf-8')
    lines = [line for line in content.splitlines() if line and not line.startswith('#')]
    # skip header, units line and separator line
    result = []
    for row in csv.reader(io.StringIO('\n'.join(lines[3:])), delimiter='\t'):
        if len(row) < 7:
            continue
        name, ra, dec, vmag, z, cl, sp = [c.strip() for c in row[:7]]
        name = ' '.join(name.split())  # catalogue names are padded, e.g. '3C  48.0'
        if not vmag or not z:
            continue
        result.append({'vcv_name': name, 'ra': ra, 'dec': dec, 'vmag': float(vmag), 'z': float(z), 'cl': cl, 'sp': sp})
    return result


def _select_objects():
    selected = {}

    for obj in _fetch_vizier([('Vmag', '<{}'.format(BRIGHT_MAG_LIMIT)), ('z', '>={}'.format(BRIGHT_MIN_Z))]):
        if obj['cl'] in ('Q', 'B'):
            selected[obj['vcv_name']] = obj

    for obj in _fetch_vizier([('Vmag', '<{}'.format(DISTANT_MAG_LIMIT)), ('z', '>={}'.format(DISTANT_MIN_Z))]):
        if obj['cl'] == 'Q':
            selected[obj['vcv_name']] = obj

    for vcv_name in FAMOUS_OBJECTS:
        found = [o for o in _fetch_vizier([('Name', '*'.join(vcv_name.split()))]) if o['vcv_name'] == vcv_name]
        if not found:
            raise ValueError('Object {} not found in {}'.format(vcv_name, VIZIER_TABLE))
        selected[vcv_name] = found[0]

    return sorted(selected.values(), key=lambda o: (o['vmag'], o['vcv_name']))


def lookback_time_gyr(z):
    zs = np.linspace(0.0, z, 10001)
    integrand = 1.0 / ((1.0 + zs) * np.sqrt(OMEGA_M * (1.0 + zs) ** 3 + (1.0 - OMEGA_M)))
    return HUBBLE_TIME_GYR * np.trapezoid(integrand, zs)


def vcv_name_to_common_name(vcv_name):
    name = ' '.join(vcv_name.split())
    if name.startswith('MARK '):
        name = 'Mrk ' + name[5:]
    if name.startswith('3C ') and name.endswith('.0'):
        name = name[:-2]
    return name


def czsky_qso_name(ra, dec):
    """ QSO + truncated J2000 coordinates, e.g. QSO1229+0203 """
    ra_h, ra_m, _ = ra.split()
    dec_d, dec_m, _ = dec.split()
    return 'QSO{}{}{}{}'.format(ra_h, ra_m, dec_d, dec_m)


def _sexagesimal_to_float(value):
    parts = [float(p) for p in value.split()]
    result = abs(parts[0]) + parts[1] / 60.0 + parts[2] / 3600.0
    return -result if value.strip().startswith('-') else result


def _assign_names(objects):
    by_name = {}
    for obj in objects:
        by_name.setdefault(czsky_qso_name(obj['ra'], obj['dec']), []).append(obj)

    for obj in objects:
        existing = EXISTING_DSOS.get(obj['vcv_name'])
        if existing:
            obj['dso_name'] = existing
            obj['is_new'] = False
            continue
        name = czsky_qso_name(obj['ra'], obj['dec'])
        same_name = sorted(by_name[name], key=lambda o: o['vcv_name'])
        if len(same_name) > 1:
            # objects closer than 1 arcmin, e.g. Twin Quasar A/B
            name += chr(ord('A') + same_name.index(obj))
        obj['dso_name'] = name
        obj['is_new'] = True


def _write_supplement(objects, output_file):
    with open(output_file, 'w', encoding='ISO-8859-1', newline='\r\n') as f:
        f.write('; Bright quasars and BL Lac objects selected from Veron-Cetty & Veron,\n')
        f.write('; Catalogue of Quasars and Active Nuclei, 13th ed. (2010), VizieR VII/258.\n')
        f.write('; Generated by czsky imports/make_bright_quasars.py. Dated {}\n'.format(date.today().isoformat()))
        f.write('; RA[hours],,,DEC[degrees],,,magn*10,name,type,brightness,length,width,orientation\n')
        for obj in objects:
            if not obj['is_new']:
                continue
            ra = _sexagesimal_to_float(obj['ra'])
            dec = _sexagesimal_to_float(obj['dec'])
            obj_type = 'QUASR/BL_Lac' if obj['cl'] == 'B' else 'QUASR'
            f.write('{:.6f},,,{:.5f},,,{:.1f},{},{},999\n'.format(ra, dec, obj['vmag'] * 10.0, obj['dso_name'], obj_type))


def _write_dso_list(objects, output_file):
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=';', lineterminator='\n')
        writer.writerow(['DSO_NAME', 'COMMON_NAME', 'RA', 'DEC', 'MAG', 'Z', 'CLASS', 'DIST', 'VCV_NAME'])
        for obj in objects:
            common_name = FAMOUS_OBJECTS.get(obj['vcv_name']) or vcv_name_to_common_name(obj['vcv_name'])
            obj_class = 'BLLAC' if obj['cl'] == 'B' else 'QSO'
            distance = lookback_time_gyr(obj['z']) * 1.0e9
            writer.writerow([obj['dso_name'], common_name, obj['ra'], obj['dec'], '{:.2f}'.format(obj['vmag']),
                             '{:.3f}'.format(obj['z']), obj_class, '{:.4e}'.format(distance), obj['vcv_name']])


def make_bright_quasars(supplement_file=SUPPLEMENT_FILE, dso_list_file=DSO_LIST_FILE):
    objects = _select_objects()
    _assign_names(objects)
    _write_supplement(objects, supplement_file)
    _write_dso_list(objects, dso_list_file)
    print('Written {} objects to {} and {} new objects to {}'.format(
        len(objects), dso_list_file, sum(1 for o in objects if o['is_new']), supplement_file))


if __name__ == '__main__':
    make_bright_quasars()
