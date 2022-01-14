import numpy as np
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.star import Star, DoubleStar
from app.models.constellation import Constellation

from .import_utils import progress


class WdsDouble:
    def __init__(self, wds_number=None, bmc_v=None, common_cat_id=None, components=None, other_designation=None,
                 first=None, last=None, num_of_publ=None, quality_score=None, bmc_q=None,
                 position_first=None, position_last=None, separation_first=None, separation_last=None,
                 mag_first=None, mag_second=None, sum_mag=None, spectral_type=None, proper_motion_ra=None,
                 proper_motion_dec=None, net_pm=None, notes=None, constell_iau= None, ra_first=None, dec_first=None):
        self.wds_number = wds_number
        self.bmc_v = bmc_v
        self.common_cat_id = common_cat_id
        self.components = components
        self.other_designation = other_designation
        self.first = first
        self.last = last
        self.num_of_publ = num_of_publ
        self.quality_score = quality_score
        self.bmc_q = bmc_q
        self.position_first = position_first
        self.position_last = position_last
        self.separation_first = separation_first
        self.separation_last = separation_last
        self.mag_first = mag_first
        self.mag_second = mag_second
        self.sum_mag = sum_mag
        self.spectral_type = spectral_type
        self.proper_motion_ra = proper_motion_ra
        self.proper_motion_dec = proper_motion_dec
        self.net_pm = net_pm
        self.notes = notes
        self.constell_iau = constell_iau
        self.ra_first = ra_first
        self.dec_first = dec_first
        self.ra_first = ra_first
        self.ref_count = 0
        self.multi_dict = None


def _parse_bmcevoy_dbl_line(line, constellation):
    wds_number = line[0:10].strip()
    bmc_v = _parse_int(line[12:26])
    common_cat_id = line[28:47].strip()
    components = line[48:61].strip()
    other_designation = line[62:148].strip()
    first = _parse_int(line[150:154])
    last = _parse_int(line[159:164])
    num_of_publ = _parse_int(line[167:181])
    quality_score = _parse_float(line[183:194])
    bmc_q = _parse_int(line[196:203])
    position_first = _parse_int(line[204:213])
    position_last = _parse_int(line[216:222])
    separation_first = _parse_float(line[234:242])
    separation_last = _parse_float(line[246:252])
    mag_first = _parse_float(line[267:277])
    mag_second = _parse_float(line[280:290])
    sum_mag = _parse_float(line[292:300])
    spectral_type = line[312:336].strip()
    proper_motion_ra = _parse_int(line[338:349])
    proper_motion_dec = _parse_int(line[350:359])
    net_pm = _parse_float(line[382:390])
    notes = line[416:470].strip()
    constell_iau= line[471:478].upper()
    ra_first = float(line[478:486].strip())*np.pi/12.0 + float(line[487:496].strip())*np.pi/(12.0*60.0) + float(line[497:506].strip())*np.pi/(12*60.0*60)
    dec_first = float(line[509]+'1')*(float(line[511:520].strip())*np.pi/180.0 + float(line[521:528].strip())*np.pi/(180.0*60) + float(line[529:542])*np.pi/(180.0*60*60))

    return WdsDouble(
        wds_number=wds_number,
        bmc_v=bmc_v,
        common_cat_id=common_cat_id,
        components=components,
        other_designation=other_designation,
        first=first,
        last=last,
        num_of_publ=num_of_publ,
        quality_score=quality_score,
        bmc_q=bmc_q,
        position_first=position_first,
        position_last=position_last,
        separation_first=separation_first,
        separation_last=separation_last,
        mag_first=mag_first,
        mag_second=mag_second,
        sum_mag=sum_mag,
        spectral_type=spectral_type,
        proper_motion_ra=proper_motion_ra,
        proper_motion_dec=proper_motion_dec,
        net_pm=net_pm,
        notes=notes,
        constell_iau= constell_iau,
        ra_first=ra_first,
        dec_first=dec_first,
    )


def import_wds_doubles(bmcevoy_filename):
    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    sf = open(bmcevoy_filename, 'r')
    lines = sf.readlines()[10:]
    sf.close()

    double_stars = []
    for line in lines:
        wds_double = _parse_bmcevoy_dbl_line(line, constell_dict)
        constellation_id = constell_dict[wds_double.constell_iau].id if wds_double.constell_iau in constell_dict else None

        double_star = DoubleStar()

        double_star.wds_number = wds_double.wds_number
        double_star.common_cat_id = wds_double.common_cat_id
        double_star.components = wds_double.components
        double_star.other_designation = wds_double.other_designation
        double_star.pos_angle = wds_double.position_last
        double_star.separation = wds_double.separation_last
        double_star.mag_first = wds_double.mag_first
        double_star.mag_second = wds_double.mag_second
        double_star.spectral_type = wds_double.spectral_type
        double_star.constellation_id = constellation_id
        double_star.ra_first = wds_double.ra_first
        double_star.dec_first = wds_double.dec_first

        double_stars.append(double_star)
    try:
        line_cnt = 1
        for double_star in double_stars:
            progress(line_cnt, len(double_stars), 'Importing WDS doubles catalogue')
            line_cnt += 1
            db.session.add(double_star)
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()


def _parse_int(val):
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return None


def _parse_float(val):
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return None
