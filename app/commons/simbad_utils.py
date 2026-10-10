from collections import OrderedDict
from threading import Lock

import numpy as np

from flask import current_app
from astroquery.simbad import Simbad

from app.commons.dso_utils import get_catalog_from_dsoname, normalize_dso_name, denormalize_dso_name
from app.commons.utils import to_float
from app.models import Constellation, IMPORT_SOURCE_SIMBAD

# ID, Label, Candidate, description
SIMBAD_OTYPE_DEFS = [
[ '*',	    'Star',		    None,   'Star', ],
[ '**',	    '**',           '**?',	'Double or Multiple Star', ],
[ 'a2*',	'alf2CVnV*',	'a2?',	'alpha2 CVn Variable', ],
[ 'AB*',	'AGB*',	        'AB?',	'Asymptotic Giant Branch Star', ],
[ 'Ae*',	'Ae*',	        'Ae?',	'Herbig Ae/Be Star', ],
[ 'AGN',	'AGN',	        'AG?',	'Active Galaxy Nucleus', ],
[ 'As*',	'Association',	'As?',	'Association of Stars', ],
[ 'bC*',	'bCepV*',	    'bC?',	'beta Cep Variable', ],
[ 'bCG',	'BlueCompactG',	None,	'Blue Compact Galaxy', ],
[ 'BD*',	'BrownD*',	    'BD?',	'Brown Dwarf', ],
[ 'Be*',	'Be*',	        'Be?',	'Be Star', ],
[ 'BH',	    'BlackHole',	'BH?',	'Black Hole', ],
[ 'BiC',	'BrightestCG',	None,	'Brightest Galaxy in a Cluster (BCG)', ],
[ 'Bla',	'Blazar',	    'Bz?',	'Blazar', ],
[ 'BLL',	'BLLac',	    'BL?',	'BL Lac', ],
[ 'blu',	'blue',		    None,   'Blue Object', ],
[ 'BS*',	'BlueStraggler','BS?',	'Blue Straggler', ],
[ 'bub',	'Bubble',		None,   'Bubble', ],
[ 'BY*',	'BYDraV*',	    'BY?',	'BY Dra Variable', ],
[ 'C*',	    'C*',	        'C*?',	'Carbon Star', ],
[ 'cC*',	'ClassicalCep',	None,   'Classical Cepheid Variable', ],
[ 'Ce*',	'Cepheid',	    'Ce?',	'Cepheid Variable', ],
[ 'CGb',	'ComGlob',		None,   'Cometary Globule / Pillar', ],
[ 'CGG',	'Compact_Gr_G',	None,	'Compact Group of Galaxies', ],
[ 'Cl*',	'Cluster*',	    'Cl?',	'Cluster of Stars', ],
[ 'Cld',	'Cloud',		None,   'Cloud', ],
[ 'ClG',	'ClG',	        'C?G',	'Cluster of Galaxies', ],
[ 'cm',	    'cmRad',		None,   'Centimetric Radio Source', ],
[ 'cor',	'denseCore',	None,	'Dense Core', ],
[ 'CV*',	'CataclyV*',	'CV?',	'Cataclysmic Binary', ],
[ 'DNe',	'DarkNeb',		None,   'Dark Cloud (nebula)', ],
[ 'dS*',	'delSctV*',		None,   'delta Sct Variable', ],
[ 'EB*',	'EclBin',	    'EB?',	'Eclipsing Binary', ],
[ 'El*',	'EllipVar',	    'El?',	'Ellipsoidal Variable', ],
[ 'Em*',	'EmLine*',		None,   'Emission-line Star', ],
[ 'EmG',	'EmissionG',	None,	'Emission-line galaxy', ],
[ 'EmO',	'EmObj',		None,   'Emission Object', ],
[ 'Er*',	'Eruptive*',	'Er?',	'Eruptive Variable', ],
[ 'err',	'Inexistent',	None,	'Not an Object (Error, Artefact, ...)', ],
[ 'ev',	    'Transient',	None,	'Transient Event', ],
[ 'Ev*',	'Evolved*',	    'Ev?',	'Evolved Star', ],
[ 'FIR',	'FarIR',		None,   'Far-IR source (? >= 30 ?m)', ],
[ 'flt',	'Filament',		None,   'Interstellar Filament', ],
[ 'G',	    'Galaxy',	    'G?',	'Galaxy', ],
[ 'gam',	'gamma',		None,   'Gamma-ray Source', ],
[ 'gB',	    'gammaBurst',	None,   'Gamma-ray Burst', ],
[ 'gD*',	'gammaDorV*',	None,	'gamma Dor Variable', ],
[ 'GiC',	'GtowardsCl',	None,	'Galaxy towards a Cluster of Galaxies', ],
[ 'GiG',	'GtowardsGroup',None,	'Galaxy towards a Group of Galaxies', ],
[ 'GiP',	'GinPair',		None,   'Galaxy in Pair of Galaxies', ],
[ 'glb',	'Globule',		None,   'Globule (low-mass dark cloud)', ],
[ 'GlC',	'GlobCluster',	'Gl?',	'Globular Cluster', ],
[ 'gLe',	'GravLens',	    'Le?',	'Gravitational Lens', ],
[ 'gLS',	'GravLensSystem','LS?',	'Gravitational Lens System (lens+images)', ],
[ 'GNe',	'GalNeb',		None,   'Nebula', ],
[ 'GrG',	'GroupG',	    'Gr?',	'Group of Galaxies', ],
[ 'grv',	'Gravitation',	None,	'Gravitational Source', ],
[ 'GWE',	'GravWaveEvent',None,	'Gravitational Wave Event', ],
[ 'H2G',	'HIIG',		    'HII',  'Galaxy', ],
[ 'HB*',	'HorBranch*',	'HB?',	'Horizontal Branch Star', ],
[ 'HH',	    'HerbigHaroObj',None,	'Herbig-Haro Object', ],
[ 'HI',	    'HI',		    None,   'HI (21cm) Source', ],
[ 'HII',	'HIIReg',		None,   'HII Region', ],
[ 'HS*',	'HotSubdwarf',	'HS?',	'Hot Subdwarf', ],
[ 'HV*',	'HighVel*',		None,   'High Velocity Star', ],
[ 'HVC',	'HVCld',		None,   'High-velocity Cloud', ],
[ 'HXB',	'HighMassXBin',	'HX?',	'High Mass X-ray Binary', ],
[ 'IG',	    'InteractingG',	None,	'Interacting Galaxies', ],
[ 'IR',	    'Infrared',		None,   'Infra-Red Source', ],
[ 'Ir*',	'IrregularV*',	None,	'Irregular Variable', ],
[ 'ISM',	'ISM',		    None,   'Interstellar Medium Object', ],
[ 'LeG',	'LensedG',		None,   'Gravitationally Lensed Image of a Galaxy', ],
[ 'LeI',	'LensedImage',	'LI?',	'Gravitationally Lensed Image', ],
[ 'LeQ',	'LensedQ',		None,   'Gravitationally Lensed Image of a Quasar', ],
[ 'Lev',	'LensingEv',	None,	'(Micro)Lensing Event', ],
[ 'LIN',	'LINER',		None,   'LINER-type Active Galaxy Nucleus', ],
[ 'LM*',	'Low-Mass*',	'LM?',	'Low-mass Star', ],
[ 'LP*',	'LongPeriodV*',	'LP?',	'Long-Period Variable', ],
[ 'LSB',	'LowSurfBrghtG',None,	'Low Surface Brightness Galaxy', ],
[ 'LXB',	'LowMassXBin',	'LX?',	'Low Mass X-ray Binary', ],
[ 'Ma*',	'Massiv*',	    'Ma?',	'Massive Star', ],
[ 'Mas',	'Maser',		None,   'Maser', ],
[ 'MGr',	'MouvGroup',	None,	'Moving Group', ],
[ 'Mi*',	'Mira',	        'Mi?',	'Mira Variable', ],
[ 'MIR',	'MidIR',		None,   'Mid-IR Source (3 to 30 ?m)', ],
[ 'mm',	    'mmRad',		None,   'Millimetric Radio Source', ],
[ 'MoC',	'MolCld',		None,   'Molecular Cloud', ],
[ 'mR',	    'metricRad',	None,	'Metric Radio Source', ],
[ 'MS*',	'MainSequence*','MS?',	'Main Sequence Star', ],
[ 'mul',	'Blend',		None,   'Composite Object, Blend', ],
[ 'N*',	    'Neutron*',	    'N*?',	'Neutron Star', ],
[ 'NIR',	'NearIR',		None,   'Near-IR Source (? < 3 ?m)', ],
[ 'No*',	'Nova',	        'No?',	'Classical Nova', ],
[ 'OH*',	'OH/IR*',	    'OH?',	'OH/IR Star', ],
[ 'OpC',	'OpenCluster',	None,	'Open Cluster', ],
[ 'Opt',	'Optical',		None,   'Optical Source', ],
[ 'Or*',	'OrionV*',		None,   'Orion Variable', ],
[ 'out',	'Outflow',	    'of?',	'Outflow', ],
[ 'pA*',	'post-AGB*',	'pA?',	'Post-AGB Star', ],
[ 'PaG',	'PairG',		None,   'Pair of Galaxies', ],
[ 'PCG',	'protoClG',	    'PCG?',	'Proto Cluster of Galaxies', ],
[ 'Pe*',	'ChemPec*',	    'Pe?',	'Chemically Peculiar Star', ],
[ 'Pl',	    'Planet',   	'Pl?',	'Extra-solar Planet', ],
[ 'PM*',	'HighPM*',		None,   'High Proper Motion Star', ],
[ 'PN',	    'PlanetaryNeb',	'PN?',	'Planetary Nebula', ],
[ 'PoC',	'PartofCloud',	None,	'Part of Cloud', ],
[ 'PoG',	'PartofG',		None,   'Part of a Galaxy', ],
[ 'Psr',	'Pulsar',		None,   'Pulsar', ],
[ 'Pu*',	'PulsV*',	    'Pu?',	'Pulsating Variable', ],
[ 'QSO',	'QSO',	        'Q?',	'Quasar', ],
[ 'Rad',	'Radio',		None,   'Radio Source', ],
[ 'rB',	    'radioBurst',	None,   'Radio Burst', ],
[ 'RC*',	'RCrBV*',	    'RC?',	'R CrB Variable', ],
[ 'reg',	'Region',		None,   'Region defined in the Sky', ],
[ 'rG',	    'RadioG',		None,   'Radio  Galaxy', ],
[ 'RG*',	'RGB*',	        'RB?',	'Red Giant Branch star', ],
[ 'RNe',	'RefNeb',		None,   'Reflection Nebula', ],
[ 'Ro*',	'RotV*',	    'Ro?',	'Rotating Variable', ],
[ 'RR*',	'RRLyrae',	    'RR?',	'RR Lyrae Variable', ],
[ 'RS*',	'RSCVnV*',	    'RS?',	'RS CVn Variable', ],
[ 'RV*',	'RVTauV*',	    'RV?',	'RV Tauri Variable', ],
[ 'S*',	    'S*',	        'S*?',	'S Star', ],
[ 's*b',	'BlueSG',	    's?b',	'Blue Supergiant', ],
[ 's*r',	'RedSG',	    's?r',	'Red Supergiant', ],
[ 's*y',	'YellowSG',	    's?y',	'Yellow Supergiant', ],
[ 'SB*',	'SB*',	        'SB?',	'Spectroscopic Binary', ],
[ 'SBG',	'StarburstG',	None,	'Starburst Galaxy', ],
[ 'SCG',	'SuperClG',	    'SC?',	'Supercluster of Galaxies', ],
[ 'SFR',	'StarFormingReg',None,	'Star Forming Region', ],
[ 'sg*',	'Supergiant',	'sg?',	'Evolved Supergiant', ],
[ 'sh',	    'HIshell',		None,   'Interstellar Shell', ],
[ 'smm',	'smmRad',		None,   'Sub-Millimetric Source', ],
[ 'SN*',	'Supernova',	'SN?',	'SuperNova', ],
[ 'SNR',	'SNRemnant',	'SR?',	'SuperNova Remnant', ],
[ 'St*',	'Stream',		None,   'Stellar Stream', ],
[ 'SX*',	'SXPheV*',		None,   'SX Phe Variable', ],
[ 'Sy*',	'Symbiotic*',	'Sy?',	'Symbiotic Star', ],
[ 'Sy1',	'Seyfert1',		None,   'Seyfert 1 Galaxy', ],
[ 'Sy2',	'Seyfert2',		None,   'Seyfert 2 Galaxy', ],
[ 'SyG',	'Seyfert',		None,   'Seyfert Galaxy', ],
[ 'TT*',	'TTauri*',	    'TT?',	'T Tauri Star', ],
[ 'ULX',	'ULX',	        'UX?',	'Ultra-luminous X-ray Source', ],
[ 'UV',	    'UV',		    None,   'UV-emission Source', ],
[ 'V*',	    'Variable*',	'V*?',	'Variable Star', ],
[ 'var',	'Variable',		None,   'Variable source', ],
[ 'vid',	'Void',		    None,   'Underdense Region of the Universe', ],
[ 'WD*',	'WhiteDwarf',	'WD?',	'White Dwarf', ],
[ 'WR*',	'WolfRayet*',	'WR?',	'Wolf-Rayet', ],
[ 'WV*',	'Type2Cep',	    'WV?',	'Type II Cepheid Variable', ],
[ 'X',	    'X',		    None,   'X-ray  Source', ],
[ 'XB*',	'XrayBin',	    'XB?',	'X-ray Binary', ],
[ 'Y*O',	'YSO',	        'Y*?',	'Young Stellar Object', ],
]

SIMBAD_TO_CZSKY = {
    'G': 'GX',
    'GNe': 'BN',
    'DNe': 'DN',
    'PN': 'PN',
    'OpC': 'OC',
    'GlC': 'GC',
    'QSO': 'QSO',
    'ClG': 'GALCL',
    '**': 'STARS',
    'As*': 'AST',
    'PoG': 'PartOf',
    'pA*':'pA*',
    'C*':'C*',
    'CV*': 'CV*',
    'RNe': 'RNe',
    'HII': 'HII'
}

SIMBAD_OTYPE_DESCRIPTIONS = {d[0]: d[3] for d in SIMBAD_OTYPE_DEFS}

# Star-like otypes (incl. candidates) that never represent a deepsky object
_NON_STELLAR_STAR_OTYPES = {'**', 'Cl*', 'As*', 'St*'}
SIMBAD_STELLAR_OTYPES = {d[0] for d in SIMBAD_OTYPE_DEFS if d[0].endswith('*') and d[0] not in _NON_STELLAR_STAR_OTYPES} | \
                        {d[2] for d in SIMBAD_OTYPE_DEFS if d[2] and d[0].endswith('*') and d[0] not in _NON_STELLAR_STAR_OTYPES}

SIMBAD_NAME_PREFIX = 'NAME '
SIMBAD_CLUSTER_PREFIX = 'Cl '

SIMBAD_CACHE_SIZE = 256

# (connect, read) timeout in seconds for HTTP requests to Simbad
SIMBAD_TIMEOUT = (3, 5)

_simbad_cache = OrderedDict()
_simbad_cache_lock = Lock()


def _to_str(value):
    if value is None or np.ma.is_masked(value):
        return None
    value = str(value).strip()
    return value or None


def _set_session_timeout(session, timeout):
    # astroquery's Simbad TAP (pyvo) issues requests without any timeout, force it on the underlying session
    request = session.request

    def request_with_timeout(method, url, **kwargs):
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = timeout
        return request(method, url, **kwargs)

    session.request = request_with_timeout


def _to_rounded_float(value, ndigits=2):
    # Simbad returns float32 values, e.g. 15.3 -> 15.300000190734863
    value = _to_str(value)
    return round(float(value), ndigits) if value is not None else None


def _query_simbad_row(query, fields):
    simbad = Simbad()
    simbad.ROW_LIMIT = 1
    _set_session_timeout(simbad._session, SIMBAD_TIMEOUT)
    simbad.add_votable_fields(*fields)
    result = simbad.query_object(query)
    return result[0] if result is not None and len(result) > 0 else None


def simbad_query(query):
    """
    Query Simbad by object identifier. Returns dict with normalized keys:
    main_id, ra, dec (radians), otype, otypes (list), ids (list), morph_type, sp_type,
    galdim_majaxis, galdim_minaxis, galdim_angle, flux_v. Returns None if not found.
    Successful results are cached in memory.
    """
    with _simbad_cache_lock:
        if query in _simbad_cache:
            _simbad_cache.move_to_end(query)
            return dict(_simbad_cache[query])

    simbad_obj = _simbad_query_uncached(query)

    if simbad_obj is not None:
        with _simbad_cache_lock:
            _simbad_cache[query] = simbad_obj
            if len(_simbad_cache) > SIMBAD_CACHE_SIZE:
                _simbad_cache.popitem(last=False)
        simbad_obj = dict(simbad_obj)
    return simbad_obj


def _simbad_query_uncached(query):
    try:
        row = _query_simbad_row(query, ('otype', 'alltypes', 'ids', 'galdim_minaxis', 'galdim_majaxis', 'galdim_angle',
                                        'sp_type', 'morph_type'))
        if row is None:
            return None
        otypes = _to_str(row['alltypes.otypes'])
        ids = _to_str(row['ids'])
        simbad_obj = {
            'main_id': ' '.join(str(row['main_id']).split()),
            'ra': float(row['ra']) * np.pi / 180.0,
            'dec': float(row['dec']) * np.pi / 180.0,
            'otype': _to_str(row['otype']),
            'otypes': otypes.split('|') if otypes else [],
            'ids': [' '.join(i.split()) for i in ids.split('|')] if ids else [],
            'morph_type': _to_str(row['morph_type']),
            'sp_type': _to_str(row['sp_type']),
            'galdim_majaxis': _to_rounded_float(row['galdim_majaxis']),
            'galdim_minaxis': _to_rounded_float(row['galdim_minaxis']),
            'galdim_angle': _to_rounded_float(row['galdim_angle']),
            'flux_v': None,
        }
    except Exception:
        current_app.logger.exception('Simbad query failed for %s', query)
        return None

    # flux fields are inner-joined in Simbad TAP, objects without V flux would be dropped from the main query
    try:
        flux_row = _query_simbad_row(query, ('V',))
        if flux_row is not None:
            simbad_obj['flux_v'] = _to_rounded_float(flux_row['V'])
    except Exception:
        current_app.logger.exception('Simbad flux query failed for %s', query)
    return simbad_obj


def get_otype_from_simbad(simbad):
    otype = simbad['otype']
    if otype in SIMBAD_TO_CZSKY:
        return SIMBAD_TO_CZSKY[otype]
    if otype in SIMBAD_STELLAR_OTYPES:
        # a star, possibly member of multiple system - secondary otypes as '**' must not turn it into DSO
        return None
    for stype in simbad['otypes']:
        if stype in SIMBAD_TO_CZSKY:
            return SIMBAD_TO_CZSKY[stype]
    return None


def _get_known_catalog(simbad_id, dso_name):
    cat = get_catalog_from_dsoname(dso_name)
    if cat is not None and simbad_id.split(' ', 1)[0].upper() == cat.code.upper():
        return cat
    return None


def _strip_prefix(simbad_id, prefix):
    return simbad_id[len(prefix):].strip() if simbad_id.startswith(prefix) else simbad_id


def get_dso_name_from_simbad(simbad):
    """
    Returns (name, common_name) for a DSO created from Simbad object. Simbad 'NAME xxx' identifiers are proper names,
    they go to common_name and designation from the most significant catalog known in czsky is used as name.
    """
    main_id = simbad['main_id']
    if not main_id.startswith(SIMBAD_NAME_PREFIX):
        return normalize_dso_name(denormalize_dso_name(_strip_prefix(main_id, SIMBAD_CLUSTER_PREFIX))), None

    common_name = _strip_prefix(main_id, SIMBAD_NAME_PREFIX)
    best_name, best_cat = None, None
    for simbad_id in simbad['ids']:
        if simbad_id.startswith(SIMBAD_NAME_PREFIX):
            continue
        simbad_id = _strip_prefix(simbad_id, SIMBAD_CLUSTER_PREFIX)
        dso_name = normalize_dso_name(denormalize_dso_name(simbad_id))
        cat = _get_known_catalog(simbad_id, dso_name)
        if cat is not None and (best_cat is None or cat.id < best_cat.id):
            best_name, best_cat = dso_name, cat
    if best_name is not None:
        return best_name, common_name
    return normalize_dso_name(denormalize_dso_name(common_name)), common_name


def get_dso_lookup_names_from_simbad(simbad):
    """ All names under which the Simbad object could be stored in the db. """
    names = [simbad['main_id']] + simbad['ids']
    for prefix in (SIMBAD_NAME_PREFIX, SIMBAD_CLUSTER_PREFIX):
        names += [_strip_prefix(n, prefix) for n in names if n.startswith(prefix)]
    return list(dict.fromkeys(names))


def simbad_obj_to_deepsky(simbad, dso):
    dso.name, common_name = get_dso_name_from_simbad(simbad)
    dso.type = get_otype_from_simbad(simbad)

    dso.subtype = simbad['morph_type']

    dso.ra = simbad['ra']
    dso.dec = simbad['dec']

    dso.constellation_id = Constellation.get_constellation_by_position(dso.ra, dso.dec).id
    cat = get_catalog_from_dsoname(dso.name)
    dso.catalogue_id = cat.id if cat else None

    major_axis = to_float(simbad['galdim_majaxis'], None)
    if major_axis is not None:
        dso.major_axis = round(major_axis * 60, 2)

    minor_axis = to_float(simbad['galdim_minaxis'], None)
    if minor_axis is not None:
        dso.minor_axis = round(minor_axis * 60, 2)

    if dso.minor_axis is not None and dso.major_axis is not None:
        dso.axis_ratio = dso.minor_axis / dso.major_axis
    else:
        dso.axis_ratio = 1.0

    dso.position_angle = to_float(simbad['galdim_angle'], None)
    dso.mag = to_float(simbad['flux_v'], 100)

    dso.surface_bright = None
    dso.c_star_b_mag = None
    dso.c_star_v_mag = None
    dso.distance = None
    dso.common_name = common_name
    dso.descr = None
    dso.import_source = IMPORT_SOURCE_SIMBAD
