import re

from app.models.catalogue import Catalogue

CATALOG_SPECS0 = { 'Sh2' }
# catalog_specs1 = {'Cannon', 'Haro', 'He', 'Hoffleit', 'Hu', 'K', 'Merrill', 'PK', 'Peimbert', 'Perek', 'Vy'}
CATALOGS_SPEC2 = ['vdB-Ha' ]

CATALOGS_SPECIFICATIONS = (
    ('Abell', 3),
    ('B', 3),
    ('Cr', 3),
    ('HCG', 3),
    ('IC', 4),
    ('LDN', 4),
    ('Mel', 3), # Must be before Messier (M) since has longer prefix
    ('M', 3),
    ('NGC', 4),
    ('Sh2-', 3),
    ('Pal', 2),
    ('PK', -1), # PK catalog has specific normalization/denormalization
    ('Stock', 2),
    ('UGC', 5),
    ('VIC', 2),
)

def split_catalog_name(dso_name):
    '''
    Split dso name to pair <catalog code, ID of dso in catalog>
    '''
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
                if i ==1 and dso_name[0] == 'M': # special handling for minkowski
                    return 'Mi', dso_name[1:]
                for prefix in CATALOG_SPECS0:
                    if dso_name.startswith(prefix):
                        return dso_name[:len(prefix)],dso_name[len(prefix):]
                return dso_name[:i],dso_name[i:]
    if not dso_name[i].isdigit():
        for prefix in CATALOGS_SPEC2:
            if dso_name.startswith(prefix):
                return dso_name[:len(prefix)],dso_name[len(prefix):]
        # print('Unknown {}'.format(dso_name))
        return None, dso_name
    return dso_name[:i], dso_name[i:]

def get_catalog_from_dsoname(dso_name):
    catalog_code, dso_id = split_catalog_name(dso_name)
    return Catalogue.get_catalogue_by_code(catalog_code)

def normalize_dso_name(dso_name):
    if not dso_name is None:
        catalog_code, dso_id = split_catalog_name(dso_name)
        if catalog_code:
            return catalog_code.upper() + dso_id
    return dso_name

def normalize_dso_name_for_img(dso_name):
    if dso_name is None:
        return dso_name

    dso_name = dso_name.replace('_','').replace(' ','')

    if dso_name.startswith('PK'):
        return dso_name

    for cat_spec in CATALOGS_SPECIFICATIONS:
        if dso_name.startswith(cat_spec[0]):
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

def denormalize_dso_name(name):
    if name.startswith('PK'):
        return 'PK ' + name[2:]
    zero_index = name.find('0')
    norm = None
    if zero_index < 0 or name[zero_index-1].isdigit():
        norm = name
    else:
        last_zero_index = zero_index
        while name[last_zero_index+1] == '0':
            last_zero_index += 1
        norm = name[:zero_index] + name[last_zero_index+1:]
    if norm.startswith('Sh2-'):
        return norm
    m = re.search("\d", norm)
    return norm[:m.start()] + ' ' + norm[m.start():] if m else norm

def destructuralize_dso_name(name):
    if name.startswith('PK'):
        return (name, None)
    if name.startswith('Sh2-'):
        return ('Sh2', name[3:])
    m = re.search("\d+", name)
    return (name[:m.start()], int(name[m.start():m.end()]))

def main_component_dso_name(dso_name):
    if (dso_name.startswith('NGC') or dso_name.startswith('IC') or dso_name.startswith('UGC')):
        if dso_name.endswith('A'):
            dso_name = dso_name[:-1]
        elif dso_name.endswith('-1') or dso_name.endswith('_1'):
            dso_name = dso_name[:-2]
    return dso_name

