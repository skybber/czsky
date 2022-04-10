import re
import numpy as np
from sqlalchemy.exc import IntegrityError
import gzip

from app import db
from app.models import Constellation, DoubleStar, Star

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

GREEK_TO_LAT = {
    "α":"alp",
    "α²": "alp 1",
    "α¹": "alp 2",

    "β":"bet",
    "β¹":"bet 1",
    "β²":"bet 2",
    "β³":"bet 3",

    "γ":"gam",
    "γ¹": "gam 1",
    "γ²": "gam 2",
    "γ³": "gam 3",

    "δ":"del",
    "δ¹": "del 1",
    "δ²": "del 2",
    "δ³": "del 3",

    "ε":"eps",
    "ε¹": "eps 1",
    "ε²": "eps 2",

    "ζ":"zet",
    "ζ¹": "zet 1",
    "ζ²": "zet 2",
    "ζ³": "zet 3",
    "ζ⁴": "zet 4",

    "η":"eta",
    "η¹": "eta 1",
    "η²": "eta 2",
    "η³": "eta 3",

    "θ":"the",
    "θ¹": "the 1",
    "θ²": "the 2",

    "ι":"iot",
    "ι¹": "iot 1",
    "ι²": "iot 2",

    "κ":"kap",
    "κ¹": "kap 1",
    "κ²": "kap 2",

    "λ":"lam",
    "λ¹": "lam 1",
    "λ²": "lam 2",

    "μ":"mu",
    "μ¹": "mu 1",
    "μ²": "mu 2",

    "ν":"nu",
    "ν¹": "nu 1",
    "ν²": "nu 2",
    "ν³": "nu 3",

    "ξ":"xi",
    "ξ¹": "xi 1",
    "ξ²": "xi 2",

    "ο":"omi",
    "ο¹": "omi 1",
    "ο²": "omi 2",

    "π":"pi",
    "π¹": "pi 1",
    "π²": "pi 2",
    "π³": "pi 3",
    "π⁴": "pi 4",
    "π⁵": "pi 5",
    "π⁶": "pi 6",

    "ρ":"rho",
    "ρ¹": "rho 1",
    "ρ²": "rho 2",
    "ρ³": "rho 3",

    "σ":"sig",
    "σ¹": "sig 1",
    "σ²": "sig 2",
    "σ³": "sig 3",

    "ς":"sig",

    "τ":"tau",
    "τ¹": "tau 1",
    "τ²": "tau 2",
    "τ³": "tau 3",
    "τ⁴": "tau 4",
    "τ⁵": "tau 5",
    "τ⁶": "tau 6",
    "τ⁷": "tau 7",
    "τ⁸": "tau 8",
    "τ⁹": "tau 9",

    "υ":"ups",
    "υ¹": "ups 1",
    "υ²": "ups 2",
    "υ⁴": "ups 3",

    "φ":"phi",
    "φ¹": "phi 1",
    "φ²": "phi 2",
    "φ³": "phi 3",
    "φ⁴": "phi 4",

    "χ":"chi",
    "χ¹": "chi 1",
    "χ²": "chi 2",
    "χ³": "chi 3",

    "ψ":"psi",
    "ψ¹": "psi 1",
    "ψ²": "psi 2",
    "ψ³": "psi 3",
    "ψ⁴": "psi 4",
    "ψ⁵": "psi 5",
    "ψ⁶": "psi 6",
    "ψ⁷": "psi 7",
    "ψ⁸": "psi 8",
    "ψ⁹": "psi 9",

    "ω":"ome",
    "ω¹": "ome 1",
    "ω²": "ome 2",
}


class WdsDouble:
    def __init__(self, wds_number=None, bmc_v=None, common_cat_id=None, components=None, other_designation=None,
                 first=None, last=None, num_of_publ=None, quality_score=None, bmc_q=None,
                 position_first=None, position_last=None, separation_first=None, separation_last=None,
                 mag_first=None, mag_second=None, sum_mag=None, delta_mag=None, spectral_type=None, proper_motion_ra=None,
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
        self.delta_mag = delta_mag
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


def _parse_bmcevoy_dbl_line(line):
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
    delta_mag = _parse_float(line[300:308])
    spectral_type = line[312:336].strip()
    proper_motion_ra = _parse_int(line[338:349])
    proper_motion_dec = _parse_int(line[350:359])
    net_pm = _parse_float(line[382:390])
    notes = line[416:470].strip()
    constell_iau = line[471:478].strip().upper()
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
        delta_mag=delta_mag,
        spectral_type=spectral_type,
        proper_motion_ra=proper_motion_ra,
        proper_motion_dec=proper_motion_dec,
        net_pm=net_pm,
        notes=notes,
        constell_iau= constell_iau,
        ra_first=ra_first,
        dec_first=dec_first,
    )


def _fix_greek(gr):
    if gr == 'tet':
        gr = 'the'
    if gr == 'alf':
        gr = 'alp'
    return gr.capitalize()


p1 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+(\d+(?:\,\d+)?)\s+([a-zA-Z]+)$')
p2 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+([a-zA-Z]+)$')
p3 = re.compile('^(\d+)\s+([a-zA-Z]+)$')
p4 = re.compile('^([a-zA-Z]+)\s+([a-zA-Z]+)$')
p5 = re.compile('^(V\d+)\s+([a-zA-Z]+)$')
p6 = re.compile('^([a-zA-Z]+)\s+(\d+(?:\,\d+)?)\s+([a-zA-Z]+)$')
p7 = re.compile('^(\d+)\s+([a-zA-Z]+)\s*,\s*(\w+)\s+([a-zA-Z]+)$')
p8 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+([a-zA-Z]+)\s*,\s*([a-zA-Z]+)\s+([a-zA-Z]+)$')
p9 = re.compile('^([a-zA-Z]+)\s+([a-zA-Z]+)\s*,\s*([a-zA-Z]+)\s+([a-zA-Z]+)$')
p10 = re.compile('^(\d+)\s+([a-zA-Z]+)\s+(\d+(?:\,\d+)?)\s+([a-zA-Z]+)\s*,\s*([a-zA-Z]+)\s+([a-zA-Z]+)$')


def _parse_other_designation(des, print_not_found):
    if not des:
        return None, None, None, None

    bayer = None
    flamsteed = None
    var_id = None
    star_name = None

    m = re.search('\(([A-Z][a-z]+)\)', des)
    if m:
        star_name = m.group(1)

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
        bayer = _fix_greek(m.group(2)) + ' ' + m.group(3) + ' ' + m.group(4)
        flamsteed = m.group(1) + ' ' + m.group(4)
        return bayer, flamsteed, var_id, star_name
    m = p2.match(des)
    if m:
        # 9 alf CMa
        flamsteed = m.group(1) + ' ' + m.group(3)
        bayer = _fix_greek(m.group(2)) + ' ' + m.group(3)
        return bayer, flamsteed, var_id, star_name
    m = p3.match(des)
    if m:
        # 27 Tau
        flamsteed = m.group(1) + ' ' + m.group(2)
        return bayer, flamsteed, var_id, star_name
    m = p4.match(des)
    if m:
        if m.group(1) in SHORT_LAT_TO_GREEK:
            bayer = _fix_greek(m.group(1)) + ' ' + m.group(2)
        else:
            var_id = m.group(1) + ' ' + m.group(2)
        return bayer, flamsteed, var_id, star_name
    m = p5.match(des)
    if m:
        # V337 Car
        var_id = m.group(1) + ' ' + m.group(2)
        return bayer, flamsteed, var_id, star_name
    m = p6.match(des)
    if m:
        # alf 1 Cru
        if m.group(1) in SHORT_LAT_TO_GREEK:
            bayer = _fix_greek(m.group(1)) + ' ' + m.group(2) + ' ' + m.group(3)
        else:
            unresolved = m.group(1) + ' ' + m.group(2) + ' ' + m.group(3)
            if print_not_found:
                print('# Unresolved1 {}'.format(unresolved))
        return bayer, flamsteed, var_id, star_name
    m = p7.match(des)
    if m:
        # 36 Oph, A Oph
        flamsteed = m.group(1) + ' ' + m.group(2)
        bayer = m.group(3) + ' ' + m.group(4)
        return bayer, flamsteed, var_id, star_name
    m = p8.match(des)
    if m:
        # 68 omi Cet, VZ Cet
        flamsteed = m.group(1) + ' ' + m.group(3)
        if m.group(2) in SHORT_LAT_TO_GREEK:
            bayer = _fix_greek(m.group(2)) + ' ' + m.group(3)
        else:
            unresolved = m.group(2) + ' ' + m.group(3)
            if print_not_found:
                print('# Unresolved2 {}'.format(unresolved))
        var_id = m.group(4) + ' ' + m.group(5)
        return bayer, flamsteed, var_id, star_name
    m = p9.match(des)
    if m:
        # sig Ori, V1030 Ori
        if m.group(1) in SHORT_LAT_TO_GREEK:
            bayer = _fix_greek(m.group(1)) + ' ' + m.group(2)
            var_id = _fix_greek(m.group(3)) + ' ' + m.group(4)
        else:
            var_id = m.group(1) + ' ' + m.group(2)
            unused = _fix_greek(m.group(3)) + ' ' + m.group(4)
            # print('####### Unused 2nd var_id={}'.format(unused))
        return bayer, flamsteed, var_id, star_name

    m = p10.match(des)
    if m:
        # 32 omi 2 Cyg, V1488 Cyg
        flamsteed = m.group(1) + ' ' + m.group(4)
        bayer = _fix_greek(m.group(2)) + ' ' + m.group(3) + ' ' + m.group(4)
        var_id = m.group(5) + ' ' + m.group(6)
        return bayer, flamsteed, var_id, star_name

    if print_not_found:
        print('# UNRESOLVED3 : {}'.format(des))
    return bayer, flamsteed, var_id, star_name


def import_wds_doubles(bmcevoy_filename, print_not_found=False):
    constell_dict = {}
    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    sf = gzip.open(bmcevoy_filename, 'rt', encoding='utf-8')
    lines = sf.readlines()[10:]
    sf.close()

    existing_stars = {}
    for star in Star.query.filter_by().all():
        if not star.constellation_id:
            continue
        constell_iau = Constellation.get_constellation_by_id(star.constellation_id).iau_code
        if star.flamsteed:
            existing_stars[str(star.flamsteed) + ' ' + constell_iau] = star
        if star.var_id:
            if star.var_id.isdigit():
                existing_stars[star.var_id + ' ' + constell_iau] = star
            else:
                existing_stars[star.var_id + ' ' + constell_iau] = star
        if star.bayer:
            str_gr = GREEK_TO_LAT.get(star.bayer)
            if str_gr:
                existing_stars[str_gr.capitalize() + ' ' + constell_iau] = star

    existing_double_stars = {}
    for double_star in DoubleStar.query.filter_by().all():
        key = double_star.wds_number
        map = existing_double_stars.get(key)
        if map is None:
            map = {}
            existing_double_stars[key] = map
        key2 = double_star.common_cat_id + '-' + (double_star.components if double_star.components else '_')
        if key2 in map:
            if print_not_found:
                print('Error key. Doublestar key is not unique: {}'.format(key + key2))
            return
        map[key2] = double_star

    double_stars = []
    for line in lines:
        wds_double = _parse_bmcevoy_dbl_line(line)

        bayer, flamsteed, var_id, star_name = _parse_other_designation(wds_double.other_designation, print_not_found)

        star = None

        if bayer or flamsteed or var_id:
            if flamsteed:
                star = existing_stars.get(flamsteed)
            if not star and var_id:
                star = existing_stars.get(var_id)
            if not star and bayer:
                star = existing_stars.get(bayer)
            if not star and print_not_found:
                print('# Star not found bayer={} flamsteed={} var_id={}'.format(bayer, flamsteed, var_id))

        double_star = None
        map = existing_double_stars.get(wds_double.wds_number)
        if map:
            key2 = wds_double.common_cat_id + '-' + (wds_double.components if wds_double.components else '_')
            double_star = map.get(key2)

        if not double_star:
            double_star = DoubleStar()

        normalized_designation = ''
        if bayer:
            normalized_designation += bayer + ';'
        if flamsteed:
            normalized_designation += flamsteed + ';'
        if var_id:
            normalized_designation += var_id + ';'
        if star_name:
            normalized_designation += star_name + ';'

        double_star.wds_number = wds_double.wds_number
        double_star.common_cat_id = wds_double.common_cat_id
        double_star.components = wds_double.components
        double_star.other_designation = wds_double.other_designation
        double_star.norm_other_designation = (';' + normalized_designation) if normalized_designation else ''
        double_star.pos_angle = wds_double.position_last
        double_star.separation = wds_double.separation_last
        double_star.mag_first = wds_double.mag_first
        double_star.mag_second = wds_double.mag_second
        double_star.delta_mag = wds_double.delta_mag
        double_star.spectral_type = wds_double.spectral_type
        double_star.constellation_id = constell_dict.get(wds_double.constell_iau)
        double_star.ra_first = wds_double.ra_first
        double_star.dec_first = wds_double.dec_first
        double_star.star_id = star.id if star else None

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
