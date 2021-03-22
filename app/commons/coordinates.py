from lat_lon_parser import parse as lonlat_parse
from wtforms.validators import ValidationError

def geoc_to_string(geoc, format_str):
    '''
    Extend GeoCoord.to_string() by 's' format
    Output lat, lon coordinates as string in chosen format
    Inputs:
        format (str) - A string of the form A%B%C where A, B and C are identifiers.
          Unknown identifiers (e.g. ' ', ', ' or '_' will be inserted as separators
          in a position corresponding to the position in format.
    Examples:
        >> palmyra = LatLon(5.8833, -162.0833)
        >> palmyra.to_string('D') # Degree decimal output
        ('5.8833', '-162.0833')
        >> palmyra.to_string('H% %D')
        ('N 5.8833', 'W 162.0833')
        >> palmyra.to_string('d%_%M')
        ('5_52.998', '-162_4.998')
    '''
    format2value = {'H': geoc.get_hemisphere(),
                    'M': abs(geoc.decimal_minute),
                    'm': int(abs(geoc.minute)),
                    'd': int(geoc.degree),
                    'D': geoc.decimal_degree,
                    'S': abs(geoc.second),
                    's': int(round(abs(geoc.second))),
                    }
    format_elements = format_str.split('%')
    coord_list = [str(format2value.get(element, element)) for element in format_elements]
    coord_str = ''.join(coord_list)
    if 'H' in format_elements: # No negative values when hemispheres are indicated
        coord_str = coord_str.replace('-', '')
    return coord_str

def latlon_to_string(lat_lon):
    format_str = 'd%° %m%′ %s%" %H'
    return geoc_to_string(lat_lon.lat, format_str) + ', ' + geoc_to_string(lat_lon.lon, format_str)


def ra_to_float(ra):
    """Convert right ascension to float."""
    return 0.0

def dec_to_float(ra):
    """Convert declination to float."""
    return 0.0

def mapy_cz_url(lon, lat):
    return 'https://www.mapy.cz/zakladni?x=' + str(lon) + '&y=' + str(lat) + '&z=17'

def google_url(lon, lat):
    return 'https://www.google.com/maps/place/' + str(lat) + ',' + str(lon)

def open_street_map_url(lon, lat):
    return 'https://www.openstreetmap.org/?mlat=' + str(lat) + '&mlon=' + str(lon) + '&zoom=12'

def parse_lonlat(coords):
    longLat = coords.split(',')
    if longLat and len(longLat) == 2:
        return (lonlat_parse(longLat[0]), lonlat_parse(longLat[1]))
    else:
        raise ValueError('Invalid coordinate format {}'.format(coords))

def lonlat_check(form, field):
    try:
        parse_lonlat(field.data)
    except ValueError:
        raise ValidationError('Invalid coordinate format.')
