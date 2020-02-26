import csv, sys
from sqlalchemy.orm.session import make_transient

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject
from skyfield.units import Angle

from .import_utils import progress

dso_type_mappings = {
    'G': 'Glx',
    'OCl' : 'OC',
    'GCl' : 'GC',
}

messier_others = {}

def import_open_ngc(open_ngc_data_file):
    """Import data from OpenNGC catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    with open(open_ngc_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        ngc_ic_list = []
        messier_list = []
        try:
            for row in reader:
                constellation = row['Const']

                if constellation in ['Se1', 'Se2']:
                    constellation = 'Ser'

                catalogue_id = None
                if row['Name'].startswith('IC'):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('IC')
                elif row['Name'].startswith('NGC'):
                    catalogue_id = Catalogue.get_catalogue_id_by_cat_code('NGC')

                dso_type = dso_type_mappings.get(row['Type'],row['Type'])

                dso = DeepskyObject.query.filter_by(name = row['Name']).first()

                if dso is None:
                    dso = DeepskyObject()

                dso.master_id = None
                dso.name = row['Name']
                dso.type = dso_type
                dso.ra = Angle(hours=tuple(map(float, row['RA'].split(':')))).radians if len(row['RA']) > 0 else None
                dso.dec = Angle(degrees=tuple(map(float, row['Dec'].split(':')))).radians if len(row['Dec']) > 0 else None
                dso.constellation_id = constell_dict[constellation] if constellation else None
                dso.catalogue_id = catalogue_id
                dso.major_axis = float(row['MajAx'])*60.0 if row['MajAx'] else None
                dso.minor_axis = float(row['MinAx'])*60.0 if row['MinAx'] else None
                dso.positon_angle = float(row['PosAng']) if row['PosAng'] else None
                dso.b_mag = float(row['B-Mag']) if row['B-Mag'] else None
                dso.v_mag = float(row['V-Mag']) if row['V-Mag'] else None
                dso.j_mag = float(row['J-Mag']) if row['J-Mag'] else None
                dso.h_mag = float(row['H-Mag']) if row['H-Mag'] else None
                dso.k_mag = float(row['K-Mag']) if row['K-Mag'] else None
                dso.surface_bright = float(row['SurfBr']) if row['SurfBr'] else None
                dso.hubble_type =  row['Hubble']
                dso.c_star_u_mag = float(row['Cstar U-Mag']) if row['Cstar U-Mag'] else None
                dso.c_star_b_mag = float(row['Cstar B-Mag']) if row['Cstar B-Mag'] else None
                dso.c_star_v_mag = float(row['Cstar V-Mag']) if row['Cstar V-Mag'] else None
                dso.identifiers = row['Identifiers']
                dso.common_name = row['Common names']
                dso.descr = row['NED notes']

                ngc_ic_list.append(dso)
                if row['M'] or dso.name=='NGC5866':
                    mes_id = row['M']

                    if not mes_id:
                        mes_id = '102'

                    mes_dso = DeepskyObject.query.filter_by(name = ('M' + mes_id)).first()
                    if mes_dso is None:
                        mes_dso = DeepskyObject()

                    mes_dso.name = 'M' + mes_id
                    mes_dso.type = dso.type
                    mes_dso.ra = dso.ra
                    mes_dso.dec = dso.dec
                    mes_dso.constellation_id = dso.constellation_id
                    mes_dso.catalogue_id = Catalogue.get_catalogue_id_by_cat_code('M')
                    mes_dso.major_axis = dso.major_axis * 60.0 if dso.major_axis else None
                    mes_dso.minor_axis = dso.minor_axis * 60.0 if dso.minor_axis else None
                    mes_dso.positon_angle = dso.positon_angle
                    mes_dso.b_mag = dso.b_mag
                    mes_dso.v_mag = dso.v_mag
                    mes_dso.j_mag = dso.j_mag
                    mes_dso.h_mag = dso.h_mag
                    mes_dso.k_mag = dso.k_mag
                    mes_dso.surface_bright = dso.surface_bright
                    mes_dso.hubble_type =  dso.hubble_type
                    mes_dso.c_star_u_mag = dso.c_star_u_mag
                    mes_dso.c_star_b_mag = dso.c_star_b_mag
                    mes_dso.c_star_v_mag = dso.c_star_v_mag
                    mes_dso.identifiers = dso.identifiers
                    mes_dso.common_name = dso.common_name
                    mes_dso.descr = dso.descr

                    dso.master_dso = mes_dso
                    messier_others[mes_dso.name] = dso
                    messier_list.append(mes_dso)

            m40 = DeepskyObject.query.filter_by(name = 'M040').first()
            if m40 is None:
                m40 = DeepskyObject()

            m40.name = 'M040'
            m40.type = '**'
            m40.ra = Angle(hours=tuple(map(float, '12:22:16'.split(':')))).radians
            m40.dec = Angle(degrees=tuple(map(float, '58:05:4'.split(':')))).radians
            m40.constellation_id = constell_dict['UMa']
            m40.catalogue_id = Catalogue.get_catalogue_id_by_cat_code('M')
            m40.major_axis = 1.0 * 60.0
            m40.minor_axis = None
            m40.positon_angle = dso.positon_angle
            m40.b_mag = None
            m40.v_mag = 9.0
            m40.j_mag = None
            m40.h_mag = None
            m40.k_mag = None
            m40.surface_bright = None
            m40.hubble_type =  None
            m40.c_star_u_mag = None
            m40.c_star_b_mag = None
            m40.c_star_v_mag = None
            m40.identifiers = None
            m40.common_name = None
            m40.descr = None

            messier_list.append(m40)

            m45 = DeepskyObject.query.filter_by(name = 'M045').first()
            if m45 is None:
                m45 = DeepskyObject()

            m45.name = 'M045'
            m45.type = 'OC'
            m45.ra = Angle(hours=tuple(map(float, '03:47:0'.split(':')))).radians
            m45.dec = Angle(degrees=tuple(map(float, '24:07:0'.split(':')))).radians
            m45.constellation_id = constell_dict['Tau']
            m45.catalogue_id = Catalogue.get_catalogue_id_by_cat_code('M')
            m45.major_axis = 95.0 * 60.0
            m45.minor_axis = 35.0 * 60.0
            m45.positon_angle = dso.positon_angle
            m45.b_mag = None
            m45.v_mag = 3.1
            m45.j_mag = None
            m45.h_mag = None
            m45.k_mag = None
            m45.surface_bright = None
            m45.hubble_type =  None
            m45.c_star_u_mag = None
            m45.c_star_b_mag = None
            m45.c_star_v_mag = None
            m45.identifiers = None
            m45.common_name = 'Pleiades'
            m45.descr = None

            messier_list.append(m45)

            messier_list.sort(key=lambda x: x.name)
            line_cnt = 1
            for mes_dso in messier_list:
                progress(line_cnt, len(messier_list), 'Importing Messier catalogue ...')
                line_cnt += 1
                db.session.add(mes_dso)
                db.session.flush()
                if mes_dso.name in messier_others:
                    messier_others[mes_dso.name].master_id = mes_dso.id
            line_cnt = 1
            print('')
            for dso in ngc_ic_list:
                progress(line_cnt, len(ngc_ic_list), 'Importing NGC/IC catalogue ...')
                line_cnt += 1
                db.session.add(dso)
            print('')
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
