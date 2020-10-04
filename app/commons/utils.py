def to_float(value, default):
    if value is not None:
        try:
            return float(value) 
        except ValueError:
            pass
    return default

def to_boolean(value, default):
    if value is not None:
        if value == '0' or value == 'False':
            return False
        return True
    return default