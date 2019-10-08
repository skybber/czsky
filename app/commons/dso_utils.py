from app import db

from app.models import DeepSkyObject

# catalogue identifier + max number of digits
catalogs_specifications = (
    ('NGC', 4),
    ('IC', 4),
    ('M', 3),
    ('ABELL', 2),
    ('SH2-', 3),
    ('VIC', 2),
)

browsing_catalogues = ('M', 'ABELL', 'VIC')

def normalize_dso_name(name):
    if name is None:
        return name
    upper_name = name.upper().replace(' ','')

    for cat_spec in catalogs_specifications:
        cat_identifier = cat_spec[0]
        if upper_name.startswith(cat_identifier):
            appendix = upper_name[len(cat_identifier):]
            applen = len(appendix)
            if applen > 0 and applen < cat_spec[1]:
                return cat_identifier + ('0' * (cat_spec[1] - applen)) + appendix
            return upper_name
    return name

def get_prev_next_dso(dso):
    prev_dso = None
    next_dso = None
    for c in browsing_catalogues:
        if dso.name.startswith(c):
            dso_id = int(dso.name[len(c):])
            if dso_id > 0:
                prev_name = normalize_dso_name(c + str(dso_id - 1))
                prev_dso = DeepSkyObject.query.filter_by(name=prev_name).first()
            next_name = normalize_dso_name(c + str(dso_id + 1))
            next_dso = DeepSkyObject.query.filter_by(name=next_name).first()
            break
    return prev_dso, next_dso