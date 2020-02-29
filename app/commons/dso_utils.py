import re

# Uppercase name / DB normalized name,/ max digits of object id
catalogs_specifications = (
    ('ABELL', 'Abell', 3),
    ('B', 'B', 3),
    ('CR', 'Cr', 3),
    ('HCG', 'HCG', 3),
    ('IC', 'IC', 4),
    ('LDN', 'LDN', 4),
    ('MEL', 'Mel', 3), # Must be before Messier (M) since has longer prefix
    ('M', 'M', 3),
    ('NGC', 'NGC', 4),
    ('SH2-', 'Sh2-', 3),
    ('PAL', 'Pal', 2),
    ('PK', 'PK', -1), # PK catalog has specific normalization/denormalization
    ('STOCK', 'Stock', 2),
    ('UGC', 'UGC', 5),
    ('VIC', 'VIC', 2),
)

def normalize_dso_name(name):
    if name is None:
        return name

    upper_name = name.upper().replace('_','').replace(' ','')

    if upper_name.startswith('PK'):
        return upper_name

    for cat_spec in catalogs_specifications:
        cat_identifier = cat_spec[0]
        if upper_name.startswith(cat_identifier):
            for i in reversed(range(len(upper_name))):
                if upper_name[i].isdigit():
                    break
            if i > 0:
                nondigit_appendix = upper_name[i+1:] if i < len(upper_name)-1 else ''
                appendix = upper_name[len(cat_identifier):i+1]
                applen = len(appendix)
                if applen > 0 and applen <= cat_spec[2]:
                    return cat_spec[1] + ('0' * (cat_spec[2] - applen)) + appendix + nondigit_appendix
            return upper_name
    return name

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
