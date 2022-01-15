import re

import numpy as np
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.star import Star
from app.models.double_star import DoubleStar
from app.models.constellation import Constellation

from .import_utils import progress

SHORT_LAT_TO_GREEK = {
    "alp":"α",
    "alf":"α",
    "bet":"β",
    "gam":"γ",
    "del":"δ",
    "eps":"ε",
    "zet":"ζ",
    "eta":"η",
    "the":"θ",
    "tet":"θ",
    "iot":"ι",
    "kap":"κ",
    "lam":"λ",
    "mu":"μ",
    "nu":"ν",
    "xi":"ξ",
    "omi":"ο",
    "pi":"π",
    "rho":"ρ",
    "sig":"σ",
    "tau":"τ",
    "ups":"υ",
    "phi":"φ",
    "chi":"χ",
    "psi":"ψ",
    "ome":"ω",
}

LONG_LAT_TO_GREEK = [
    ("Alpha","alp"),
    ("Beta","bet"),
    ("Gamma","gam"),
    ("Delta","del"),
    ("Epsilon","eps"),
    ("Zeta","zet"),
    ("Eta","eta"),
    ("Theta","the"),
    ("Iota","iot"),
    ("Kappa","kap"),
    ("Lambda","lam"),
    ("Mu","mu"),
    ("Nu","nu"),
    ("Xi","xi"),
    ("Omicron","omi"),
    ("Pi","pi"),
    ("Rho","rho"),
    ("Sigma","sig"),
    ("Tau","tau"),
    ("Upsilon","ups"),
    ("Phi","phi"),
    ("Chi","chi"),
    ("Psi","psi"),
    ("Omega","ome"),
]

HELP_MAP = {
    'Alp Her': ('Alp 1,2 Her', None, None),
    'Zet Cnc': ('STF 1196', 'Zet Cnc', 'AB'),
    'Bet 1 Cas': ('AGC 15', 'Bet Cas', 'AB'),
    'Eta Tau': ('STFA 8', 'Eta Tau', 'AB')
}


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


wds_doubles_by_common_cat_id = {}
wds_doubles_by_other_designation = {}


def _parse_bmcevoy_dbl(filename, constell_dict):
    wds_stars = []
    sf = open(filename, 'r')
    lines = sf.readlines()[10:]
    sf.close()

    p1 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+(\d+)\s+([a-zA-Z]+)$')
    p2 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+([a-zA-Z]+)$')
    p3 = re.compile('^(\d+)\s+([a-zA-Z]+)$')
    p4 = re.compile('^([a-zA-Z]+)\s+([a-zA-Z]+)$')
    p5 = re.compile('^(V\d+)\s+([a-zA-Z]+)$')
    p6 = re.compile('^([a-zA-Z]+)\s+(\d+)\s+([a-zA-Z]+)$')
    p7 = re.compile('^(\d+)\s+([a-zA-Z]+),\s*(\w+)\s+([a-zA-Z]+)$')
    p8 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+([a-zA-Z]+)\s*,\s*([a-zA-Z]+)\s+([a-zA-Z]+)$')
    p9 = re.compile('^([a-zA-Z]+)\s+([a-zA-Z]+)\s*,\s*([a-zA-Z]+)\s+([a-zA-Z]+)$')

    for line in lines:
        wds_double = _parse_bmcevoy_dbl_line(line, constell_dict)

        constellation_id = constell_dict[wds_double.constell_iau].id if wds_double.constell_iau in constell_dict else None

        if wds_double.common_cat_id not in wds_doubles_by_common_cat_id:
            multi_dict = {}
            wds_doubles_by_common_cat_id[wds_double.common_cat_id] = multi_dict
        else:
            multi_dict = wds_doubles_by_common_cat_id[wds_double.common_cat_id]
        wds_double.multi_dict = multi_dict
        key = wds_double.components if wds_double.components else '_'
        multi_dict[key] = wds_double
        if wds_double.other_designation:
            des = wds_double.other_designation
            i1 = des.find('(')
            while i1 >= 0:
                i2 = des.find(')')
                if i2 >= 0 and i2 > i1:
                    if i2 + 1 < len(des):
                        des = des[:i1] + des[i2+1:]
                    else:
                        des = des[:i1]
                    des = des.strip()
                    i1 = des.find('(')
                else:
                    break
            m = p1.match(des)
            if m:
                # 9 alf 2 Lib
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(4)] = wds_double
                wds_doubles_by_other_designation[_fix_greek(m.group(2)) + ' ' + m.group(3) + ' ' + m.group(4)] = wds_double
                continue
            m = p2.match(des)
            if m:
                # 9 alf CMa
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(3)] = wds_double
                wds_doubles_by_other_designation[_fix_greek(m.group(2)) + ' ' + m.group(3)] = wds_double
            m = p3.match(des)
            if m:
                # 27 Tau
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(2)] = wds_double
                continue
            m = p4.match(des)
            if m:
                if m.group(1) in SHORT_LAT_TO_GREEK:
                    wds_doubles_by_other_designation[_fix_greek(m.group(1)) + ' ' + m.group(2)] = wds_double
                else:
                    # var ID
                    wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(2)] = wds_double
                continue
            m = p5.match(des)
            if m:
                # V337 Car
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(2)] = wds_double
                continue
            m = p6.match(des)
            if m:
                # alf 1 Cru
                if m.group(1) in SHORT_LAT_TO_GREEK:
                    wds_doubles_by_other_designation[_fix_greek(m.group(1)) + ' ' + m.group(2) + ' ' + m.group(3)] = wds_double
                else:
                    pass
                    #print('{}'.format(des))
                continue
            m = p7.match(des)
            if m:
                # 36 Oph, A Oph
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(2)] = wds_double
                wds_doubles_by_other_designation[m.group(3) + ' ' + m.group(4)] = wds_double
                continue
            m = p8.match(des)
            if m:
                # 68 omi Cet, VZ Cet
                wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(3)] = wds_double
                if m.group(2) in SHORT_LAT_TO_GREEK:
                    wds_doubles_by_other_designation[_fix_greek(m.group(2)) + ' ' + m.group(3)] = wds_double
                else:
                    wds_doubles_by_other_designation[m.group(2) + ' ' + m.group(3)] = wds_double
                wds_doubles_by_other_designation[m.group(4) + ' ' + m.group(5)] = wds_double
                continue
            m = p9.match(des)
            if m:
                # sig Ori, V1030 Ori
                if m.group(1) in SHORT_LAT_TO_GREEK:
                    wds_doubles_by_other_designation[_fix_greek(m.group(1)) + ' ' + m.group(2)] = wds_double
                else:
                    wds_doubles_by_other_designation[m.group(1) + ' ' + m.group(2)] = wds_double
                wds_doubles_by_other_designation[_fix_greek(m.group(3)) + ' ' + m.group(4)] = wds_double
                continue
            # print('{}'.format(des))


def _fix_greek(gr):
    if gr == 'tet':
        gr = 'the'
    if gr == 'alf':
        gr = 'alp'
    return gr.capitalize()


def _parse_sac_dbl_line(line, constell_dict):
    constell = constell_dict[line[1:4].strip()]
    name = line[5:20].strip()

    ra = float(line[21:23])*np.pi/12.0 + float(line[24:28])*np.pi/(12.0*60.0)
    dec = float(line[29]+'1')*(float(line[30:32])*np.pi/180.0 + float(line[33:35]) * np.pi/(180.0*60.0))

    comp = line[36:40].strip()
    other_names = line[41:67].strip()

    mag = _parse_float(line[68:72])
    mag2 = _parse_float(line[73:77])
    separation = _parse_float(line[78:83])
    position_angle = _parse_int(line[84:87])

    notes = line[88: 149].strip()

    sao = _parse_int(line[162:168])

    wds_double = None

    name = _normalize_name(name)

    if comp:
        comp = comp.replace('x', ',')
        comp = comp.replace('X', ',')

    if name in HELP_MAP:
        name, other_names2, comp_cond = HELP_MAP[name]
        if other_names2 and comp_cond == comp:
            other_names = other_names2

    if name:
        wds_double = _get_from_wds_doubles_by_common_cat_id(name, comp)
        if not wds_double and other_names:
            other_names_parts = other_names.split(';')
            wds_double = _get_from_wds_doubles_by_common_cat_id(_normalize_name(other_names_parts[0].strip()), comp)
            if not wds_double and len(other_names_parts) > 1:
                wds_double = _get_from_wds_doubles_by_common_cat_id(_normalize_name(other_names_parts[1].strip()), comp)
        if not wds_double:
            wds_double = _get_from_wds_doubles_by_other_designation(name, comp)

    if not wds_double and other_names:
        wds_double = _get_from_wds_doubles_by_other_designation(other_names, comp)

    if wds_double:
        if wds_double.ref_count == 1:
            print('//// Wds multi ref name={} other_names={}'.format(name, other_names))
            pass
        wds_double.ref_count += 1
    else:
        print('Wds not found name={} other_names={}'.format(name, other_names))
        return None

    return None

    star = Star(
        src_catalogu='sac_doubles',
        hr=None,
        bayer_flamsteed=None,
        hd=None,
        sao=sao,
        fk5=None,
        multiple=line[43:44].strip(),
        var_id=None,
        ra=ra,
        dec=dec,
        mag=mag,
        bv=None,
        sp_type=None,
        dmag=mag2-mag,
        sep=separation,
        mult_id=comp,
        mult_cnt=None
    )
    return star


def _normalize_name(name):
    while '  ' in name:
        name = name.replace('  ', ' ')

    for gr_pair in LONG_LAT_TO_GREEK:
        if gr_pair[0] in name:
            repl = gr_pair[1].capitalize()
            name = name.replace(gr_pair[0], repl)
            if name[len(repl)].isdigit() and (name[len(repl)+1] == ' '):
                name = name[0:len(repl)] + ' ' + name[len(repl):]
            break

    name = name.replace('Burnham', 'BU')
    name = name.replace('Dunlop', 'DUN')
    name = name.replace('Howe', 'HWE')
    name = name.replace('South', 'S')

    if name.startswith('Roe '):
        name = 'ROE' + name[3:]

    if name.startswith('h '):
        name = 'HJ' + name[1:]

    if name.startswith('Sh '):
        name = 'SHJ' + name[2:]

    return name


def _get_from_wds_doubles_by_common_cat_id(name, comp):
    multi_dict = wds_doubles_by_common_cat_id.get(name)
    if multi_dict:
        return _lookup_multi_dict(multi_dict, name, comp)
    return None


def _get_from_wds_doubles_by_other_designation(name, comp):
    name_parts = name.split(';')
    pivot_double = wds_doubles_by_other_designation.get(name_parts[0].strip())
    if not pivot_double and len(name_parts) > 1:
        pivot_double = wds_doubles_by_other_designation.get(name_parts[1].strip())

    if pivot_double:
        return _lookup_multi_dict(pivot_double.multi_dict, name, comp)
    return None


def _lookup_multi_dict(multi_dict, name, comp):
    if comp:
        wds_double = multi_dict.get(comp)
        if not wds_double:
            if len(multi_dict) == 1:
                wds_double = list(multi_dict.values())[0]
                print('++++ Getting first as default for name={} comp={} keys={}'.format(name, comp, list(multi_dict.keys())))
            else:
                print('---- Not found {} {} keys={}'.format(name, comp, list(multi_dict.keys())))
    else:
        if len(multi_dict) == 1:
            wds_double = list(multi_dict.values())[0]
        else:
            wds_double = multi_dict.get('_')
            if not wds_double:
                wds_double = multi_dict.get('AB')
                if not wds_double:
                    wds_double = list(multi_dict.values())[0]
                    print('++++ Getting first as default for name={}'.format(name))
                else:
                    pass
                    # print('---- Geting AB as default for name={}'.format(name))
    return wds_double


def import_sac_doubles(sac_filename, bmcevoy_filename):

    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    _parse_bmcevoy_dbl(bmcevoy_filename, constell_dict)

    stars = []

    sf = open(sac_filename, 'r')
    lines = sf.readlines()[1:]
    sf.close()

    for line in lines:
        star = _parse_sac_dbl_line(line, constell_dict)
        if star:
            stars.append(star)

    try:
        line_cnt = 1
        for star in stars:
            progress(line_cnt, len(stars), 'Importing SAc dooubles catalogue')
            line_cnt += 1
            db.session.add(star)
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
