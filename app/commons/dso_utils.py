import re
from io import BytesIO

from app.models.catalogue import Catalogue

CATALOG_REPLACEMENTS = [
    (re.compile(re.escape('barnard'), re.IGNORECASE), 'B'),
    (re.compile(re.escape('hickson'), re.IGNORECASE), 'HCG')
]

CATALOG_SPECS0 = {'sh2'}
# catalog_specs1 = {'Cannon', 'Haro', 'He', 'Hoffleit', 'Hu', 'K', 'Merrill', 'PK', 'Peimbert', 'Perek', 'Vy'}
CATALOGS_SPEC2 = ['vdb-ha']

CATALOGS_SPECIFICATIONS = (
    ('Abell', 3),
    ('B', 3),
    ('Cr', 3),
    ('HCG', 3),
    ('IC', 4),
    ('LDN', 4),
    ('Mel', 3),  # Must be before Messier (M) since has longer prefix
    ('M', 3),
    ('NGC', 4),
    ('Sh2-', 3),
    ('Pal', 2),
    ('PK', -1),  # PK catalog has specific normalization/denormalization
    ('Stock', 2),
    ('UGC', 5),
    ('VIC', 2),
)

CHART_STAR_PREFIX = '_st_'
CHART_DOUBLE_STAR_PREFIX = '_dst_'
CHART_PLANET_PREFIX = '_pl_'
CHART_COMET_PREFIX = '_com_'
CHART_MINOR_PLANET_PREFIX = '_mpl_'

PK_NUM_PATTERN = re.compile(r'([+-])0+(\d+).0+(\d+)')


def split_catalog_name(dso_name):
    """
    Split dso name to pair <catalog code, ID of dso in catalog>
    """
    dso_name = dso_name.replace(' ', '')
    i = 0
    name_len = len(dso_name)
    while i < name_len:
        if not dso_name[i].isalpha():
            break
        i += 1
    else:
        return None, dso_name

    # if dso_name[:i] in catalog_specs1:
    #    return dso_name[:i],dso_name[i:]

    if dso_name[i].isdigit():
        if i < name_len - 1:
            if dso_name[i+1] == '-' or dso_name[i+1] == '_':
                if i == 1 and dso_name[0] in ['M', 'm']:  # special handling for minkowski
                    return 'Mi', dso_name[1:]
                lower_dso_name = dso_name.lower()
                for prefix in CATALOG_SPECS0:
                    if lower_dso_name.startswith(prefix):
                        return dso_name[:len(prefix)], dso_name[len(prefix):]
                return dso_name[:i], dso_name[i:]
    if not dso_name[i].isdigit():
        lower_dso_name = dso_name.lower()
        for prefix in CATALOGS_SPEC2:
            if lower_dso_name.startswith(prefix):
                return dso_name[:len(prefix)], dso_name[len(prefix):]
        # print('Unknown {}'.format(dso_name))
        return None, dso_name
    return dso_name[:i], dso_name[i:]


def get_catalog_from_dsoname(dso_name):
    catalog_code, dso_id = split_catalog_name(dso_name)
    return Catalogue.get_catalogue_by_code(catalog_code)


def normalize_dso_name_ext(dso_name):
    for repl_pair in CATALOG_REPLACEMENTS:
        dso_name = repl_pair[0].sub(repl_pair[1], dso_name)
    return normalize_dso_name(dso_name)


def normalize_dso_name(dso_name):
    if dso_name is not None:
        cat_code, dso_id = split_catalog_name(dso_name)
        if cat_code:
            norm_cat_code = Catalogue.get_catalogue_code(cat_code)
            if norm_cat_code == 'Mi':
                norm_cat_code = 'M'
            return Catalogue.get_catalogue_code(norm_cat_code) + dso_id
    return dso_name


def normalize_double_star_name(double_star_name):
    norm = _unzero(double_star_name.strip())
    m = re.search("\\d", norm)
    return norm[:m.start()].replace(' ', '') + ' ' + norm[m.start():].replace('  ', ' ') if m else norm


def normalize_supernova_name(supernove_name):
    norm = supernove_name.strip().replace(' ', '')
    return norm


def normalize_dso_name_for_img(dso_name):
    if dso_name is None:
        return dso_name

    dso_name = dso_name.replace('_', '').replace(' ', '')

    if dso_name.startswith('PK'):
        return dso_name

    for cat_spec in CATALOGS_SPECIFICATIONS:
        if dso_name.startswith(cat_spec[0]):
            i = 0
            for i in reversed(range(len(dso_name))):
                if dso_name[i].isdigit():
                    break
            if i > 0:
                nondigit_appendix = dso_name[i+1:] if i < len(dso_name)-1 else ''
                appendix = dso_name[len(cat_spec[0]):i+1]
                applen = len(appendix)
                if applen > 0 and applen <= cat_spec[1]:
                    return cat_spec[0] + ('0' * (cat_spec[1] - applen)) + appendix + nondigit_appendix
            return dso_name
    return dso_name


def _unzero(name):
    eat_zero = False
    result = ''
    for i in range(len(name)):
        c = name[i]
        if c == '0':
            if not eat_zero:
                if i > 0 and not name[i-1].isdigit():
                    eat_zero = True
            if not eat_zero:
                result += '0'
        else:
            if eat_zero and not c.isdigit():
                result += '0'
            eat_zero = False
            result += c
    if eat_zero:
        result += '0'
    return result


def denormalize_dso_name(name):
    norm = _unzero(name.strip())
    if norm.startswith('Sh2-'):
        return norm
    m = re.search("\\d", norm)
    return norm[:m.start()].replace(' ', '') + ' ' + norm[m.start():].replace(' ', '') if m else norm


def destructuralize_dso_name(name):
    if name.startswith('PK'):
        return name, None
    if name.startswith('Sh2-'):
        return 'Sh2', name[4:]
    m = re.search("\\d+", name)
    return name[:m.start()], int(name[m.start():m.end()])


def main_component_dso_name(dso_name):
    if dso_name.startswith('NGC') or dso_name.startswith('IC') or dso_name.startswith('UGC'):
        if dso_name.endswith('A'):
            dso_name = dso_name[:-1]
        elif dso_name.endswith('-1') or dso_name.endswith('_1'):
            dso_name = dso_name[:-2]
    return dso_name


def dso_name_to_simbad_id(name):
    if name.startswith('PK'):
        return 'PK_' + name[2:]
    if name.startswith('Abell') and len(name)<=7:
        return 'PN_A66' + name[5:]
    if name.startswith('K1-') or name.startswith('K2-') or name.startswith('K3-') or \
       name.startswith('M1-') or name.startswith('M2-') or name.startswith('M3-') or name.startswith('M4-') or \
       name.startswith('DeHt') or name.startswith('Hoffleit')  or name.startswith('Hu') or name.startswith('Sa') or name.startswith('Vy') or \
       name.startswith('IRAS') or name.startswith('Kr'):
        return 'PN_' + name
    return name

def dso_name_from_visible_obj_name(dso_name):
    if dso_name.isdigit():
        dso_name = 'NGC' + dso_name
    elif re.match(r'^\d*_\d$', dso_name):
        dso_name = 'NGC' + dso_name
    return dso_name

def get_norm_visible_objects_set(visible_objects):
    result = set()
    for dso_name in visible_objects[::5]:
        dso_name = dso_name_from_visible_obj_name(dso_name)
        result.add(normalize_dso_name(denormalize_dso_name(dso_name)))
    return result

def chart_items_to_file(chart_items):
    chart_items = sorted(chart_items, key=lambda x: x[1])

    mem = BytesIO()
    for chart_item in chart_items:
        line = chart_item[0] + ',' + str(chart_item[1]) + '\n'
        mem.write(line.encode('utf-8'))
    mem.seek(0)
    return mem
