import csv, sys
from sqlalchemy.orm.session import make_transient

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject
from skyfield.units import Angle

from .import_utils import progress

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

                dso = DeepSkyObject(
                    master_id = None,
                    name = row['Name'],
                    type = row['Type'],
                    ra = Angle(hours=tuple(map(float, row['RA'].split(':')))).radians if len(row['RA']) > 0 else None,
                    dec = Angle(degrees=tuple(map(float, row['Dec'].split(':')))).radians if len(row['Dec']) > 0 else None,
                    constellation_id = constell_dict[constellation] if constellation else None,
                    catalogue_id = catalogue_id,
                    major_axis = float(row['MajAx']) if row['MajAx'] else None,
                    minor_axis = float(row['MinAx']) if row['MinAx'] else None,
                    positon_angle = float(row['PosAng']) if row['PosAng'] else None,
                    b_mag = float(row['B-Mag']) if row['B-Mag'] else None,
                    v_mag = float(row['V-Mag']) if row['V-Mag'] else None,
                    j_mag =
                     float(row['J-Mag']) if row['J-Mag'] else None,
                    h_mag = float(row['H-Mag']) if row['H-Mag'] else None,
                    k_mag = float(row['K-Mag']) if row['K-Mag'] else None,
                    surface_bright = float(row['SurfBr']) if row['SurfBr'] else None,
                    hubble_type =  row['Hubble'],
                    c_star_u_mag = float(row['Cstar U-Mag']) if row['Cstar U-Mag'] else None,
                    c_star_b_mag = float(row['Cstar B-Mag']) if row['Cstar B-Mag'] else None,
                    c_star_v_mag = float(row['Cstar V-Mag']) if row['Cstar V-Mag'] else None,
                    identifiers = row['Identifiers'],
                    common_name = row['Common names'],
                    descr = row['NED notes'],
                    )
                ngc_ic_list.append(dso)
                if row['M']:
                    mes_dso = DeepSkyObject(
                        name = 'M' + row['M'],
                        type = dso.type,
                        ra = dso.ra,
                        dec = dso.dec,
                        constellation_id = dso.constellation_id,
                        catalogue_id = Catalogue.get_catalogue_id_by_cat_code('M'),
                        major_axis = dso.major_axis,
                        minor_axis = dso.minor_axis,
                        positon_angle = dso.positon_angle,
                        b_mag = dso.b_mag,
                        v_mag = dso.v_mag,
                        j_mag = dso.j_mag,
                        h_mag = dso.h_mag,
                        k_mag = dso.k_mag,
                        surface_bright = dso.surface_bright,
                        hubble_type =  dso.hubble_type,
                        c_star_u_mag = dso.c_star_u_mag,
                        c_star_b_mag = dso.c_star_b_mag,
                        c_star_v_mag = dso.c_star_v_mag,
                        identifiers = dso.identifiers,
                        common_name = dso.common_name,
                        descr = dso.descr
                        )
                    dso.master_dso = mes_dso
                    mes_dso.slave_dso = dso
                    messier_list.append(mes_dso)

            messier_list.sort(key=lambda x: x.name)
            line_cnt = 1
            for mes_dso in messier_list:
                progress(line_cnt, len(messier_list), 'Importing Messier catalogue ...')
                line_cnt += 1
                db.session.add(mes_dso)
                db.session.flush()
                mes_dso.slave_dso.master_id = mes_dso.id
            line_cnt = 1
            print('')
            for dso in ngc_ic_list:
                progress(line_cnt, len(ngc_ic_list), 'Importing NGC/IC catalogue ...')
                line_cnt += 1
                db.session.add(dso)
            print('')
            print('Committing...')
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()
