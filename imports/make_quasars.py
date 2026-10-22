"""
Generates quasar data for czsky:

  - data/supplements/Quasars, Milliquas 8 and Veron-Cetty & Veron 13.sup
      HNSKY supplement with new QSO objects. Used by the DB import and by the chart engine (fchart3).
  - data/quasars.csv
      Common names, redshifts and distances of objects in the supplement (HNSKY format can't hold them).
  - data/dsolist/BrightQuasars.csv
      DSO list "Bright quasars".

Sources:
  - Milliquas v8 (Flesch 2023, VizieR VII/294): type I quasars (Q) and BL Lac objects (B) with V <= 17.5.
    V is estimated from Milliquas photographic magnitudes as (B + R) / 2 with B-R color limited to
    MAX_COLOR_BR - a larger color usually means wrong photometry (blend) of one band, so the fainter
    magnitude is preferred.
  - Veron-Cetty & Veron 13th ed. (VizieR VII/258) for the "Bright quasars" DSO list:
      - quasars and BL Lac objects brighter than V=15.0 with z >= 0.15
        (lower z objects are mostly nuclei of galaxies already present in the DSO catalogue)
      - distant quasars with z >= 2.5 brighter than V=16.5
      - well-known objects listed in FAMOUS_OBJECTS

DSO list objects take precedence over Milliquas objects at the same position. Milliquas objects are skipped if
  - closer than EXISTING_DSO_RADIUS_ARCSEC to an existing HNSKY or PGC object - galaxy nuclei or quasars already
    present (often misclassified as galaxies in PGC)
  - z < HOST_GALAXY_MAX_Z and inside the extent of an existing galaxy - nucleus of the galaxy
  - brighter than MIN_ABS_MAG - unphysical, wrong photometry or redshift
Objects in EXISTING_DSOS are already in the DSO catalogue, the DSO list refers to the existing objects.

New objects are named QSO + truncated J2000 coordinates (QSOhhmm+ddmm). Objects sharing the same name get
suffix A, B, ... ordered by right ascension.

Distance is the light-travel distance (lookback time) for Planck 2018 cosmology in light years.

Usage: python -m imports.make_quasars
"""
import csv
import io
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

import numpy as np

VIZIER_URL = 'https://vizier.cds.unistra.fr/viz-bin/asu-tsv'
VCV_TABLE = 'VII/258/vv10'
VCV_COLUMNS = 'Name,RAJ2000,DEJ2000,Vmag,z,Cl,Sp'
MILLIQUAS_TABLE = 'VII/294/catalog'
MILLIQUAS_COLUMNS = 'RAJ2000,DEJ2000,Name,Type,Rmag,Bmag,z'

SUPPLEMENT_FILE = 'data/supplements/Quasars, Milliquas 8 and Veron-Cetty & Veron 13.sup'
QUASARS_DATA_FILE = 'data/quasars.csv'
DSO_LIST_FILE = 'data/dsolist/BrightQuasars.csv'
HNSKY_FILE = 'data/deep_sky.hnd'
PGC_FILE = 'data/PGC.dat'
PGC_UPDATE_FILE = 'data/PGC_update.dat'

MILLIQUAS_MAG_LIMIT = 17.5
# Milliquas query limit on R, V = (B + R) / 2 is brighter than R for quasars with B > R
MILLIQUAS_QUERY_R_LIMIT = 18.5
MILLIQUAS_TYPES = ('Q', 'B')

LIST_BRIGHT_MAG_LIMIT = 15.0
LIST_BRIGHT_MIN_Z = 0.15
LIST_DISTANT_MAG_LIMIT = 16.5
LIST_DISTANT_MIN_Z = 2.5

MAX_COLOR_BR = 1.5
SAME_OBJECT_RADIUS_ARCSEC = 6.0
EXISTING_DSO_RADIUS_ARCSEC = 6.0
HOST_GALAXY_MAX_Z = 0.1
# the most luminous unlensed quasars have M_V about -30.5
MIN_ABS_MAG = -31.5

# Planck 2018 flat LambdaCDM (radiation neglected)
H0 = 67.66
OMEGA_M = 0.30966
HUBBLE_TIME_GYR = 977.792 / H0
HUBBLE_DISTANCE_MPC = 299792.458 / H0

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


class PositionIndex:
    """ Simple declination band index for cross-matching small radii. Positions in degrees. """

    BAND = 1.0 / 60.0

    def __init__(self):
        self._bands = defaultdict(list)

    def add(self, ra, dec, item):
        self._bands[math.floor(dec / self.BAND)].append((ra, dec, item))

    def nearest(self, ra, dec, radius_arcsec):
        band = math.floor(dec / self.BAND)
        best, best_sep = None, None
        for b in (band - 1, band, band + 1):
            for ra2, dec2, item in self._bands.get(b, ()):
                sep = angular_separation_arcsec(ra, dec, ra2, dec2)
                if sep <= radius_arcsec and (best_sep is None or sep < best_sep):
                    best, best_sep = item, sep
        return best


class ExtentIndex:
    """ Index of objects with angular extent. Positions in degrees, radius in arcsec. """

    BAND = 1.0 / 60.0

    def __init__(self):
        self._bands = defaultdict(list)

    def add(self, ra, dec, radius_arcsec, item):
        radius_deg = radius_arcsec / 3600.0
        for b in range(math.floor((dec - radius_deg) / self.BAND), math.floor((dec + radius_deg) / self.BAND) + 1):
            self._bands[b].append((ra, dec, radius_arcsec, item))

    def containing(self, ra, dec):
        for ra2, dec2, radius_arcsec, item in self._bands.get(math.floor(dec / self.BAND), ()):
            if angular_separation_arcsec(ra, dec, ra2, dec2) <= radius_arcsec:
                return item
        return None


def angular_separation_arcsec(ra1, dec1, ra2, dec2):
    ra1, dec1, ra2, dec2 = map(math.radians, (ra1, dec1, ra2, dec2))
    # haversine, precise for small separations
    h = math.sin((dec2 - dec1) / 2.0) ** 2 + math.cos(dec1) * math.cos(dec2) * math.sin((ra2 - ra1) / 2.0) ** 2
    return math.degrees(2.0 * math.asin(min(1.0, math.sqrt(h)))) * 3600.0


def _fetch_vizier(table, columns, constraints):
    params = [('-source', table), ('-out', columns), ('-out.max', 'unlimited')] + constraints
    url = VIZIER_URL + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=600) as resp:
        content = resp.read().decode('utf-8')
    lines = [line for line in content.splitlines() if line and not line.startswith('#')]
    # skip header, units line and separator line
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO('\n'.join(lines[3:])), delimiter='\t')]


def _float_or_none(value):
    return float(value) if value else None


def _fetch_vcv(constraints):
    result = []
    for row in _fetch_vizier(VCV_TABLE, VCV_COLUMNS, constraints):
        if len(row) < 7:
            continue
        name, ra, dec, vmag, z, cl, sp = row[:7]
        if not vmag or not z:
            continue
        result.append({
            'cat_name': ' '.join(name.split()),  # catalogue names are padded, e.g. '3C  48.0'
            'ra': sexagesimal_to_float(ra) * 15.0,
            'dec': sexagesimal_to_float(dec),
            'vmag': float(vmag),
            'z': float(z),
            'bllac': cl == 'B',
            'cl': cl,
        })
    return result


def _select_list_objects():
    selected = {}

    for obj in _fetch_vcv([('Vmag', '<{}'.format(LIST_BRIGHT_MAG_LIMIT)), ('z', '>={}'.format(LIST_BRIGHT_MIN_Z))]):
        if obj['cl'] in ('Q', 'B'):
            selected[obj['cat_name']] = obj

    for obj in _fetch_vcv([('Vmag', '<{}'.format(LIST_DISTANT_MAG_LIMIT)), ('z', '>={}'.format(LIST_DISTANT_MIN_Z))]):
        if obj['cl'] == 'Q':
            selected[obj['cat_name']] = obj

    for cat_name in FAMOUS_OBJECTS:
        found = [o for o in _fetch_vcv([('Name', '*'.join(cat_name.split()))]) if o['cat_name'] == cat_name]
        if not found:
            raise ValueError('Object {} not found in {}'.format(cat_name, VCV_TABLE))
        selected[cat_name] = found[0]

    for obj in selected.values():
        obj['common_name'] = FAMOUS_OBJECTS.get(obj['cat_name']) or catalog_name_to_common_name(obj['cat_name'])
        obj['source'] = 'VCV13'

    return sorted(selected.values(), key=lambda o: (o['vmag'], o['cat_name']))


def milliquas_vmag(rmag, bmag):
    if rmag is not None and bmag is not None:
        return max(rmag, bmag) - min(abs(bmag - rmag), MAX_COLOR_BR) / 2.0
    return rmag if rmag is not None else bmag


def _fetch_milliquas():
    result = []
    for row in _fetch_vizier(MILLIQUAS_TABLE, MILLIQUAS_COLUMNS, [('Rmag', '<{}'.format(MILLIQUAS_QUERY_R_LIMIT))]):
        if len(row) < 7:
            continue
        ra, dec, name, obj_type, rmag, bmag, z = row[:7]
        if obj_type[:1] not in MILLIQUAS_TYPES:
            continue
        vmag = milliquas_vmag(_float_or_none(rmag), _float_or_none(bmag))
        if vmag is None or vmag > MILLIQUAS_MAG_LIMIT:
            continue
        cat_name = ' '.join(name.split())
        result.append({
            'cat_name': cat_name,
            'common_name': catalog_name_to_common_name(cat_name),
            'ra': float(ra),
            'dec': float(dec),
            'vmag': vmag,
            'z': _float_or_none(z),
            'bllac': obj_type.startswith('B'),
            'source': 'MQ8',
        })
    return result


def _load_existing_dso_indexes():
    from fchart3.deepsky_object import DsoType
    from fchart3.hnsky_deepsky import import_hnsky_deepsky
    from fchart3.pgc_deepsky import import_pgc_deepsky

    all_dsos = {}
    dsos = import_hnsky_deepsky(HNSKY_FILE, None, all_dsos) + \
        import_pgc_deepsky(PGC_FILE, PGC_UPDATE_FILE, None, all_dsos)
    position_index = PositionIndex()
    galaxy_index = ExtentIndex()
    for dso in dsos:
        ra, dec = math.degrees(dso.ra), math.degrees(dso.dec)
        position_index.add(ra, dec, dso)
        if dso.type == DsoType.G and dso.rlong is not None and dso.rlong > 0:
            galaxy_index.add(ra, dec, math.degrees(dso.rlong) * 3600.0, dso)
    return position_index, galaxy_index


def select_milliquas_objects(milliquas_objects, list_objects, existing_dso_index, galaxy_index):
    """
    Returns Milliquas objects not present in the DSO list, not coincident with an existing DSO
    and with plausible brightness.
    """
    list_index = PositionIndex()
    for obj in list_objects:
        list_index.add(obj['ra'], obj['dec'], obj)

    result = []
    skipped = defaultdict(int)
    for obj in milliquas_objects:
        if list_index.nearest(obj['ra'], obj['dec'], SAME_OBJECT_RADIUS_ARCSEC) is not None:
            continue
        if existing_dso_index.nearest(obj['ra'], obj['dec'], EXISTING_DSO_RADIUS_ARCSEC) is not None:
            skipped['coincident with existing DSO'] += 1
            continue
        z = obj.get('z')
        if z is not None and z < HOST_GALAXY_MAX_Z and galaxy_index.containing(obj['ra'], obj['dec']) is not None:
            skipped['nucleus of existing galaxy'] += 1
            continue
        if z is not None and z > 0 and absolute_mag(obj['vmag'], z) < MIN_ABS_MAG:
            skipped['unphysical brightness'] += 1
            continue
        result.append(obj)
    for reason, count in skipped.items():
        print('Skipped {} Milliquas objects: {}'.format(count, reason))
    return result


def lookback_time_gyr(z):
    zs = np.linspace(0.0, z, 10001)
    integrand = 1.0 / ((1.0 + zs) * np.sqrt(OMEGA_M * (1.0 + zs) ** 3 + (1.0 - OMEGA_M)))
    return HUBBLE_TIME_GYR * np.trapezoid(integrand, zs)


def luminosity_distance_mpc(z):
    zs = np.linspace(0.0, z, 10001)
    integrand = 1.0 / np.sqrt(OMEGA_M * (1.0 + zs) ** 3 + (1.0 - OMEGA_M))
    return (1.0 + z) * HUBBLE_DISTANCE_MPC * np.trapezoid(integrand, zs)


def absolute_mag(mag, z):
    """ Absolute magnitude without K-correction """
    return mag - 5.0 * math.log10(luminosity_distance_mpc(z) * 1.0e5)


def catalog_name_to_common_name(cat_name):
    name = ' '.join(cat_name.split())
    if name.startswith('MARK '):
        name = 'Mrk ' + name[5:]
    if name.startswith('3C ') and name.endswith('.0'):
        name = name[:-2]
    return name


def sexagesimal_to_float(value):
    parts = [float(p) for p in value.split()]
    result = abs(parts[0]) + parts[1] / 60.0 + parts[2] / 3600.0
    return -result if value.strip().startswith('-') else result


def czsky_qso_name(ra, dec):
    """ QSO + truncated J2000 coordinates, e.g. QSO1229+0203. ra, dec in degrees """
    ra_min = int(math.floor(round(ra / 15.0 * 60.0, 6))) % (24 * 60)
    dec_min = int(math.floor(round(abs(dec) * 60.0, 6)))
    return 'QSO{:02d}{:02d}{}{:02d}{:02d}'.format(ra_min // 60, ra_min % 60, '-' if dec < 0 else '+',
                                                  dec_min // 60, dec_min % 60)


def assign_names(objects):
    """ Set 'dso_name' and 'is_new' to all objects. """
    by_name = defaultdict(list)
    for obj in objects:
        existing = EXISTING_DSOS.get(obj['cat_name']) if obj['source'] == 'VCV13' else None
        if existing:
            obj['dso_name'] = existing
            obj['is_new'] = False
        else:
            by_name[czsky_qso_name(obj['ra'], obj['dec'])].append(obj)
            obj['is_new'] = True

    for name, same_name in by_name.items():
        if len(same_name) == 1:
            same_name[0]['dso_name'] = name
            continue
        same_name.sort(key=lambda o: (o['ra'], o['dec']))
        for i, obj in enumerate(same_name):
            obj['dso_name'] = name + chr(ord('A') + i)


def write_supplement(objects, output_file):
    new_objects = sorted((o for o in objects if o['is_new']), key=lambda o: o['dso_name'])
    with open(output_file, 'w', encoding='ISO-8859-1', newline='\n') as f:
        f.write('; Quasars and BL Lac objects from Milliquas v8 (Flesch 2023, VizieR VII/294), V=(B+R)/2 <= {}\n'
                .format(MILLIQUAS_MAG_LIMIT))
        f.write('; and bright quasars from Veron-Cetty & Veron 13th ed. (2010, VizieR VII/258).\n')
        f.write('; Generated by czsky imports/make_quasars.py. Dated {}\n'.format(date.today().isoformat()))
        f.write('; RA[hours],,,DEC[degrees],,,magn*10,name,type,brightness,length,width,orientation\n')
        for obj in new_objects:
            obj_type = 'QUASR/BL_Lac' if obj['bllac'] else 'QUASR'
            f.write('{:.6f},,,{:.5f},,,{:.1f},{},{},999\n'.format(obj['ra'] / 15.0, obj['dec'], obj['vmag'] * 10.0,
                                                                 obj['dso_name'], obj_type))
    return len(new_objects)


def _distance(obj):
    return lookback_time_gyr(obj['z']) * 1.0e9 if obj.get('z') is not None and obj['z'] > 0 else None


def write_quasars_data(objects, output_file):
    new_objects = sorted((o for o in objects if o['is_new']), key=lambda o: o['dso_name'])
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', lineterminator='\n')
        writer.writerow(['DSO_NAME', 'COMMON_NAME', 'MAG', 'Z', 'CLASS', 'DIST', 'SOURCE'])
        for obj in new_objects:
            distance = _distance(obj)
            writer.writerow([obj['dso_name'], obj['common_name'], '{:.2f}'.format(obj['vmag']),
                             '{:.3f}'.format(obj['z']) if obj.get('z') is not None else '',
                             'BLLAC' if obj['bllac'] else 'QSO',
                             '{:.4e}'.format(distance) if distance else '', obj['source']])


def write_dso_list(list_objects, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', lineterminator='\n')
        writer.writerow(['DSO_NAME', 'COMMON_NAME', 'MAG', 'Z', 'CLASS', 'DIST', 'CAT_NAME'])
        for obj in list_objects:
            writer.writerow([obj['dso_name'], obj['common_name'], '{:.2f}'.format(obj['vmag']),
                             '{:.3f}'.format(obj['z']), 'BLLAC' if obj['bllac'] else 'QSO',
                             '{:.4e}'.format(_distance(obj)), obj['cat_name']])


def make_quasars(supplement_file=SUPPLEMENT_FILE, quasars_data_file=QUASARS_DATA_FILE, dso_list_file=DSO_LIST_FILE):
    list_objects = _select_list_objects()
    print('Selected {} DSO list objects from {}'.format(len(list_objects), VCV_TABLE))

    milliquas_objects = _fetch_milliquas()
    print('Fetched {} objects from {}'.format(len(milliquas_objects), MILLIQUAS_TABLE))

    milliquas_objects = select_milliquas_objects(milliquas_objects, list_objects, *_load_existing_dso_indexes())

    all_objects = list_objects + milliquas_objects
    assign_names(all_objects)

    count = write_supplement(all_objects, supplement_file)
    write_quasars_data(all_objects, quasars_data_file)
    write_dso_list(list_objects, dso_list_file)
    print('Written {} new objects to {} and {}, {} objects to {}'.format(
        count, supplement_file, quasars_data_file, len(list_objects), dso_list_file))


if __name__ == '__main__':
    make_quasars()
