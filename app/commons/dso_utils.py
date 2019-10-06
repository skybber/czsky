# catalogue identifier + max number of digits
catalogs_specifications = [
    ['NGC', 4],
    ['IC', 4],
    ['M', 3],
    ['ABELL', 2],
    ['VIC', 2],
]

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
