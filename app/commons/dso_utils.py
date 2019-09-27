
def normalize_dso_name(name):
    if name is None:
        return name
    upper_name = name.upper().replace(' ','')
    if upper_name.startswith('NGC'):
        appendix = upper_name[3:]
        if len(appendix) < 4:
            return 'NGC' + ('0' * (4 - len(appendix))) + appendix
    if upper_name.startswith('IC'):
        appendix = upper_name[2:]
        if len(appendix) < 4:
            return 'IC' + ('0' * (4 - len(appendix))) + appendix
    return name
