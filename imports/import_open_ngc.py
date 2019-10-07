import csv, sys
from sqlalchemy.orm.session import make_transient

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepSkyObject,DsoCatalogueLink

def import_open_ngc(open_ngc_data_file):
    """Import data from OpenNGC catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code] = co.id

    catal_dict = {}

    for ca in Catalogue.query.all():
        catal_dict[ca.code] = ca

    with open(open_ngc_data_file) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        print('Importing OpenNGC catalog ...')
        messiers = []
        try:
            for row in reader:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    constellation = row['Const']

                    if constellation in ['Se1', 'Se2']:
                        constellation = 'Ser'

                    dso = DeepSkyObject(
                        name = row['Name'],
                        type = row['Type'],
                        ra = row['RA'],
                        dec = row['Dec'],
                        constellation_id = constell_dict[constellation] if constellation else None,
                        major_axis = float(row['MajAx']) if row['MajAx'] else None,
                        minor_axis = float(row['MinAx']) if row['MinAx'] else None,
                        positon_angle = float(row['PosAng']) if row['PosAng'] else None,
                        b_mag = float(row['B-Mag']) if row['B-Mag'] else None,
                        v_mag = float(row['V-Mag']) if row['V-Mag'] else None,
                        j_mag = float(row['J-Mag']) if row['J-Mag'] else None,
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
                    db.session.add(dso)
                    db.session.flush()
                    catal_id = None
                    if row['Name'].startswith('IC'):
                        catal_id = catal_dict['IC'].id
                    elif row['Name'].startswith('NGC'):
                        catal_id = catal_dict['NGC'].id
                    if catal_id is not None:
                        l = DsoCatalogueLink(
                            catalogue_id = catal_id,
                            dso_id = dso.id,
                            name = row['Name']
                            )
                        db.session.add(l)
                    if row['M']:
                        mes_dso = DeepSkyObject(
                            name = 'M' + row['M'],
                            type = dso.type,
                            ra = dso.ra,
                            dec = dso.dec,
                            constellation_id = dso.constellation_id,
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
                        messiers.append(mes_dso)
            db.session.commit()
            messiers.sort(key=lambda x: x.name)
            for mes_dso in messiers:
                db.session.add(mes_dso)
                db.session.flush()
                l = DsoCatalogueLink(
                    catalogue_id = catal_dict['M'].id,
                    dso_id = mes_dso.id,
                    name = mes_dso.name
                    )
                db.session.add(l)
            db.session.commit()
        except KeyError as err:
            print('\nKey error: {}'.format(err))
            db.session.rollback()
        except IntegrityError as err:
            print('\nIntegrity error {}'.format(err))
            db.session.rollback()

        print('') # finish on new line
