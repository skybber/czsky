import numpy as np

from astroquery.simbad import Simbad

from app.commons.dso_utils import get_catalog_from_dsoname
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

def simbad_query(query):
    try:
        Simbad.ROW_LIMIT=1
        simbad = Simbad()
        simbad.TIMEOUT = 5
        simbad.add_votable_fields('ids', 'otype', 'dim_minaxis' , 'dim_majaxis', 'dim_angle', 'sptype', 'sao', 'otypes', 'morphtype',
                                  'flux(U)', 'flux(B)', 'flux(V)', 'flux(R)', 'flux(J)', 'flux(H)', 'flux(K)', )
        simbad_obj = simbad.query_object(query)
        return simbad_obj
    except:
        return None

def get_otype_from_simbad(simbad):
    if simbad['OTYPES']:
        for stype in simbad['OTYPES'].split('|'):
            if stype in SIMBAD_TO_CZSKY:
                return SIMBAD_TO_CZSKY[stype]
    return None

def simbad_obj_to_deepsky(simbad, dso):
    dso.name = simbad['MAIN_ID'].replace(' ', '')
    dso.type = get_otype_from_simbad(simbad)

    dso.subtype = simbad['MORPH_TYPE']

    ra_segm = simbad['RA'].split(' ')
    dso.ra = float(ra_segm[0]) * np.pi / 12.0
    if len(ra_segm) > 1:
        dso.ra += float(ra_segm[1]) * np.pi / (12.0 * 60.0)
    if len(ra_segm) > 2:
        dso.ra += float(ra_segm[2]) * np.pi / (12 * 60.0 * 60)

    dec_segm = simbad['DEC'].split(' ')
    dso.dec = float(dec_segm[0]) * np.pi / 180.0
    mul_dec = 1 if dso.dec >= 0 else -1
    if len(dec_segm) > 1:
        dso.dec += mul_dec * float(dec_segm[1]) * np.pi / (180.0 * 60)
    if len(dec_segm) > 2:
        dso.dec += mul_dec * float(dec_segm[2]) * np.pi / (180.0 * 60 * 60)

    dso.constellation_id = Constellation.get_constellation_by_position(dso.ra, dso.dec).id
    cat = get_catalog_from_dsoname(dso.name)
    dso.catalogue_id = cat.id if cat else None

    major_axis = to_float(simbad['GALDIM_MAJAXIS'], None)
    if major_axis is not None:
        dso.major_axis = major_axis * 60

    minor_axis = to_float(simbad['GALDIM_MINAXIS'], None)
    if minor_axis is not None:
        dso.minor_axis = minor_axis * 60

    if dso.minor_axis is not None and dso.major_axis is not None:
        dso.axis_ratio = dso.minor_axis / dso.major_axis
    else:
        dso.axis_ratio = 1.0

    dso.position_angle = to_float(simbad['GALDIM_ANGLE'], None)
    dso.mag = to_float(simbad['FLUX_V'], 100)

    dso.surface_bright = None
    dso.c_star_b_mag = None
    dso.c_star_v_mag = None
    dso.distance = None
    dso.common_name = None
    dso.descr = None
    dso.import_source = IMPORT_SOURCE_SIMBAD
