import json

from sqlalchemy.exc import IntegrityError

import numpy as np
from skyfield.api import load_constellation_map, position_of_radec

from app import db
from app.models.star import Star
from app.models.constellation import Constellation

from .import_utils import progress


def _parse_bsc5_json_rec(rec, star_cnt, all_cnt, constell_dict, constell_lookup):
    hr = int(rec.get('HR')) if rec.get('HR') else None
    hd = int(rec.get('HD')) if rec.get('HD') else None
    sao = int(rec.get('SAO')) if rec.get('SAO') else None
    fk5 = int(rec.get('FK5')) if rec.get('FK5') else None
    bv = float(rec.get('B-V')) if rec.get('B-V') else None
    mag = float(rec.get('Vmag')) if rec.get('Vmag') else None
    dmag = float(rec.get('Dmag')) if rec.get('Dmag') else None
    sep = float(rec.get('Sep')) if rec.get('Sep') else None
    mult_cnt = int(rec.get('MultCnt')) if rec.get('MultCnt') else None

    sRA = rec.get('RA')
    sDEC = rec.get('Dec')

    if sRA and sDEC:
        ra = float(sRA[0:2])*np.pi/12.0 + float(sRA[4:6])*np.pi/(12.0*60.0) + float(sRA[8:12])*np.pi/(12*60.0*60)
        dec = float(sDEC[0:3])*np.pi/180.0
        if dec > 0:
            dec += float(sDEC[5:7])*np.pi/(180.0*60) + float(sDEC[9:11])*np.pi/(180.0*60*60)
        else:
            dec -= float(sDEC[5:7])*np.pi/(180.0*60) + float(sDEC[9:11])*np.pi/(180.0*60*60)

    else:
        ra = None
        dec = None
        mag = None

    constell_id = constell_dict.get(rec.get('Constellation')) if rec.get('Constellation') else None
    star = Star.query.filter(Star.hr==hr).first()

    # if ra and dec and not constell_id:
    #     found_iau_code = constell_lookup(position_of_radec(180*ra/np.pi, 180*dec/np.pi))
    #     if found_iau_code:
    #         constell_id = constell_dict[found_iau_code]

    if not star:
        star = Star()

    star.hr = hr
    star.constellation_id = constell_id
    star.common_name = rec.get('Common')
    star.bayer = rec.get('Bayer')
    star.flamsteed = rec.get('Flamsteed')
    star.hd = hd
    star.sao = sao
    star.fk5 = fk5
    star.multiple = rec.get('Multiple')
    star.ads = rec.get('Ads')
    star.ads_comp = ''
    star.var_id = rec.get('VarID')
    star.ra = ra
    star.dec = dec
    star.mag = mag
    star.bv = bv
    star.sp_type = rec.get('SpType')
    star.dmag = dmag
    star.sep = sep
    star.mult_id = rec.get('MultID')
    star.mult_cnt = mult_cnt
    progress(star_cnt, all_cnt, 'Importing Bsc5 catalogue from JSON')
    db.session.add(star)

    return star

def import_bright_stars_bsc5_json_all(filename):

    constell_dict = {}
    constell_lookup = load_constellation_map()

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    star_cnt = 0
    try:
        with open(filename) as f:
            all_recs = json.load(f)
            for json_rec in all_recs:
                star_cnt += 1
                _parse_bsc5_json_rec(json_rec, star_cnt, len(all_recs), constell_dict, constell_lookup)
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
