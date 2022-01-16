import csv
import sys
import numpy as np

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Constellation, Star, Catalogue, DeepskyObject
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
from skyfield.api import position_from_radec, load_constellation_map

from .import_utils import progress


def fix_cstar_from_open_ngc(open_ngc_data_file):
    """
    Get missing cstar data from openngc
    """

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    existing_dsos = {}
    for dso in DeepskyObject.query.filter_by().all():
        existing_dsos[dso.name] = dso

    row_count = sum(1 for line in open(open_ngc_data_file)) - 1

    with open(open_ngc_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        try:
            row_id = 0
            for row in reader:
                progress(row_id, row_count, 'Fixing CStar from OpenNGC')
                row_id += 1
                dso_name = denormalize_dso_name(row['Name']).replace(' ', '')

                dso = existing_dsos.get(dso_name, None)

                if dso is None:
                    continue

                dso.c_star_b_mag = float(row['Cstar B-Mag']) if row['Cstar B-Mag'] else None
                dso.c_star_v_mag = float(row['Cstar V-Mag']) if row['Cstar V-Mag'] else None
                dso.common_name = row['Common names']
                dso.descr = row['NED notes']

                db.session.add(dso)

                if row['M'] or dso.name=='NGC5866':
                    mes_id = row['M']

                    if not mes_id:
                        mes_id = '102'

                    mes_dso = existing_dsos.get('M' + mes_id.lstrip('0'), None)
                    if mes_dso is None:
                        continue

                    mes_dso.constellation_id = dso.constellation_id
                    mes_dso.c_star_b_mag = dso.c_star_b_mag
                    mes_dso.c_star_v_mag = dso.c_star_v_mag
                    mes_dso.common_name = dso.common_name
                    mes_dso.descr = dso.descr

                    db.session.add(mes_dso)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
        print('')


def fix_dso_constellation():
    constell_dict = {}

    constellation_at = load_constellation_map()

    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    try:
        for dso in DeepskyObject.query.all():
            const_code = constellation_at(position_from_radec(dso.ra / np.pi * 12.0, dso.dec / np.pi * 180.0))
            dso.constellation_id = constell_dict[const_code.upper()] if const_code else None
            db.session.add(dso)
        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('')


def _parse_pn_list_line(line):
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
      hr=int(line[:4].strip()),
      bayer_flamsteed=line[4:14].strip(),
      hd=hd,
      sao=sao,
      fk5=fk5,
      multiple=line[43:44].strip(),
      var_id=line[51:60].strip(),
      ra=ra,
      dec=dec,
      mag=mag,
      bv=bv,
      sp_type=line[127:147].strip(),
      dmag=dmag,
      sep=sep,
      mult_id=line[190:194].strip(),
      mult_cnt=mult_cnt
    )
    return star


def check_from_pn_list(pn_list_file):
    
    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    cat_codes = {}
    catalogs = Catalogue.query.filter(Catalogue.id<1000).order_by(Catalogue.id)
    for cat in catalogs:
        cat_codes[cat.id-1] = cat.code
        
    stars = []
    sf = open(pn_list_file, 'r')
    lines = sf.readlines()[1:]
    sf.close()

    for line in lines:
    
        if line[40:42].strip() != '':
            ra = float(line[40:42])*np.pi/12.0 + float(line[43:45])*np.pi/(12.0*60.0) + float(line[46:47])*np.pi/(12*60.0*60)
            dec = float(line[49]+'1')*(float(line[50:52])*np.pi/180.0 + float(line[53:55])*np.pi/(180.0*60))
        else:
            ra = None
            dec = None
            mag = None
        
        ssize = line[55:67].strip()
        if ssize == 'stellar':
            major_axis = 1
            minor_axis = 1
        else:
            major_axis = None
            minor_axis = None
            spl = ssize.split('x')
            if len(spl) >= 1:
                major = float(spl[0]) if len(spl[0]) > 0 else None
                if len(spl) > 1:
                    minor = float(spl[1]) if len(spl[1]) > 0 else None
                    
        smag = line[82:90].strip()
        if smag.endswith('p'):
            smag=smag[:-1]
        mag = float(smag) if smag else None
        
        ssurface_bright = line[97:105].strip() 
        surface_bright = float(ssurface_bright) if ssurface_bright else None
        
        cstar_mag = line[90:97].strip()

        sub_type = line[76:83].strip()

        dso = DeepskyObject(
            name=line[0:15].strip().replace(' ', ''),
            ra=ra,
            dec=dec,
            constellation_id=constell_dict.get(line[105:111].strip().upper(), None),
            catalogue_id=None,
            major_axis=major_axis,
            minor_axis=minor_axis,
            positon_angle=None,
            mag=mag,
            surface_bright=surface_bright,
            c_star_b_mag=cstar_mag,
            c_star_v_mag=cstar_mag,
        )
        
        existing_dso = DeepskyObject.query.filter_by(name=dso.name).first()
        if not existing_dso: 
            pk_num = line[15:23].strip()
            pkid = 'PK' + _denormalize_pk_name(pk_num) if pk_num else None
            if pkid:
                existing_dso = DeepskyObject.query.filter_by(name=pkid).first()
                
                if not existing_dso:
                    print('{},NOT_FOUND,'.format(dso.name))
#                 else:
#                     print('{} not found.Using PK={}'.format(dso.name, pkid))
                
        if existing_dso:
            existing_mag = _norm_mag(existing_dso.mag)
            new_mag = _norm_mag(dso.mag)
            if existing_mag == new_mag:
                # print('{} OK'.format(existing_dso.name))
                pass
            else:
                if new_mag < 100.0:
                    print('{},{:.2f},{:.2f}'.format(existing_dso.name, existing_mag, new_mag))


def _norm_mag(mag):
    if mag is None:
        return 100.0
    if mag > 99.9:
        return 100.0
    return mag


def _denormalize_pk_name(name):
    denorm = ''
    compress = True
    outp = False
    for i in range(0, len(name)):
        c = name[i]
        if compress and c == '0':
            continue 
        if not c.isdigit():
            if not outp:
                denorm += '0'
            compress = True
            outp = False
        else:
            outp = True
            compress = False
        denorm += c
    return denorm