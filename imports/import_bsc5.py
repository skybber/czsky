import numpy as np

from app import db
from app.models.star import Star

from .import_utils import progress

def _parse_bsc5_line(line):

    str_hd = line[25:31].strip()
    hd = int(str_hd) if str_hd != '' else None

    str_sao = line[31:37].strip()
    sao = int(str_sao) if str_sao != '' else None

    str_bv = line[109:114].strip()
    bv = float(str_bv[0]+'1') * float(str_bv[1:]) if str_bv != '' else None

    str_fk5 = line[37:41].strip()
    fk5 = int(str_fk5) if str_fk5 != '' else None

    str_mag = line[102:107].rstrip()
    mag = float(str_mag[0]+'1') * float(str_mag[1:]) if str_mag != '' else None

    str_dmag = line[180:184].strip()
    dmag = float(str_dmag) if str_dmag != '' else None

    str_sep = line[184:190].strip()
    sep = float(str_sep) if str_sep != '' else None

    str_mult_cnt = line[194:196].strip()
    mult_cnt = int(str_mult_cnt) if str_mult_cnt != '' else None

    if line[75:77].strip() != '':
        ra = float(line[75:77])*np.pi/12.0 + float(line[77:79])*np.pi/(12.0*60.0) + float(line[79:83])*np.pi/(12*60.0*60)
        dec = float(line[83]+'1')*(float(line[84:86])*np.pi/180.0 + float(line[86:88])*np.pi/(180.0*60) + float(line[88:90])*np.pi/(180.0*60*60))
    else:
        ra = None
        dec = None
        mag = None

    star = Star(
      hr = int(line[:4].strip()),
      bayer_flamsteed = line[4:14].strip(),
      hd = hd,
      sao = sao,
      fk5 = fk5,
      multiple = line[43:44].strip(),
      ads = line[44:49].strip(),
      ads_comp = line[44:51].strip(),
      var_id = line[51:60].strip(),
      ra = ra,
      dec = dec,
      mag = mag,
      bv = bv,
      sp_type = line[127:147].strip(),
      dmag = dmag,
      sep = sep,
      mult_id = line[190:194].strip(),
      mult_cnt = mult_cnt
    )
    return star

def import_bright_stars_bsc5(filename):
    from sqlalchemy.exc import IntegrityError

    stars = []
    sf = open(filename, 'r')
    lines = sf.readlines()
    sf.close()

    for line in lines:
        star = _parse_bsc5_line(line)
        if star:
            stars.append(star)

    try:
        line_cnt = 1
        for star in stars:
            progress(line_cnt, len(stars), 'Importing Bsc5 catalogue')
            line_cnt += 1
            db.session.add(star)
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
