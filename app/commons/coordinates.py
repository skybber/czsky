import re
import math
from lat_lon_parser import parse as lonlat_parse
from wtforms.validators import ValidationError
from skyfield.units import Angle

r_radec = re.compile(r'''(\d\d?)[h:]?[ ]?(\d\d?)[m:]?[ ]?(\d\d?(\.\d\d?\d?)?)[s:]?[ ]*([+-]?\d\d)[:°]?[ ]?(\d\d?)[:′']?[ ]?(\d\d?(\.\d\d?\d?)?)[″"]?''')


def geoc_to_string(geoc, format_str):
    """
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
    """
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


def mapy_cz_url(lon, lat):
    return 'https://www.mapy.cz/zakladni?x=' + str(lon) + '&y=' + str(lat) + '&z=17'


def google_url(lon, lat):
    return 'https://www.google.com/maps/place/' + str(lat) + ',' + str(lon)


def open_street_map_url(lon, lat):
    return 'https://www.openstreetmap.org/?mlat=' + str(lat) + '&mlon=' + str(lon) + '&zoom=12'


def parse_latlon(coords):
    lat_lon = coords.split(',')
    if lat_lon and len(lat_lon) == 2:
        return lonlat_parse(lat_lon[0]), lonlat_parse(lat_lon[1])
    else:
        raise ValueError('Invalid coordinate format {}'.format(coords))


def lonlat_check(form, field):
    try:
        parse_latlon(field.data)
    except ValueError:
        raise ValidationError('Invalid coordinate format.')


def radec_check(form, field):
    if field.data:
        try:
            ra, dec = parse_radec(field.data)
        except ValueError:
            raise ValidationError('Invalid coordinate format.')


def parse_radec(str_radec):
    global r_radec
    m = r_radec.match(str_radec)
    if m is not None:
        ra = math.pi * (int(m.group(1))/12 + int(m.group(2))/(12*60) + float(m.group(3))/(12*60*60))
        dec_base = int(m.group(5))/180
        multipl = -1.0 if m.group(5).startswith('-') else 1.0
        dec = math.pi * (dec_base + multipl * (int(m.group(6))/(180*60) + float(m.group(7))/(180*60*60)))
        return ra, dec
    raise ValueError('Invalid ra-dec format {}'.format(str_radec))


def radec_to_string_short(ra, dec):
    if ra is not None and dec is not None:
        sgn, d, m, s = Angle(radians=dec).signed_dms(warn=False)
        sign = '-' if sgn < 0.0 else '+'
        str_dec = '%s%02d:%02d:%02d' % (sign, d, m, s)
        str_ra = '%02d:%02d:%02d' % Angle(radians=ra).hms(warn=False)
        return str_ra + ' ' + str_dec
    return ''


def ra_to_str_short(ra):
    if ra:
        return '%02d:%02d:%02d' % Angle(radians=ra).hms(warn=False)
    return 'nan'


def dec_to_str_short(dec):
    if dec:
        sgn, d, m, s = Angle(radians=dec).signed_dms(warn=False)
        sign = '-' if sgn < 0.0 else '+'
        return '%s%02d:%02d:%02d' % (sign, d, m, s)
    return 'nan'


def ra_to_str(ra):
    if ra:
        return '%02d:%02d:%04.1f' % Angle(radians=ra).hms(warn=False)
    return 'nan'


def dec_to_str(dec):
    if dec:
        sgn, d, m, s = Angle(radians=dec).signed_dms(warn=False)
        sign = '-' if sgn < 0.0 else '+'
        return '%s%02d:%02d:%04.1f' % (sign, d, m, s)
    return 'nan'
