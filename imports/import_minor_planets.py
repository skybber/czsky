from sqlalchemy.exc import IntegrityError

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import db

from app.models.minor_planet import MinorPlanet
from .import_utils import progress


def import_mpcorb_minor_planets(mpcorb_file):
    with load.open(mpcorb_file) as f:
        all_minor_planets = mpc.load_mpcorb_dataframe(f)
        bad_orbits = all_minor_planets.semimajor_axis_au.isnull()
        all_minor_planets = all_minor_planets[~bad_orbits]
        all_minor_planets['minor_planet_id'] = all_minor_planets['designation_packed']

        minor_planets = []
        
        for index, mpc_mp in all_minor_planets.iterrows():
            int_designation = int(mpc_mp['designation_packed'])
            minor_planet = MinorPlanet.query.filter_by(int_designation=int_designation).first()
            if minor_planet is None:
                minor_planet = MinorPlanet()
            minor_planet.int_designation = int_designation
            minor_planet.magnitude_H = mpc_mp['magnitude_H']
            minor_planet.magnitude_G = mpc_mp['magnitude_G']
            minor_planet.epoch = mpc_mp['epoch_packed']
            minor_planet.mean_anomaly_degrees = mpc_mp['mean_anomaly_degrees']
            minor_planet.argument_of_perihelion_degrees = mpc_mp['argument_of_perihelion_degrees']
            minor_planet.longitude_of_ascending_node_degrees = mpc_mp['longitude_of_ascending_node_degrees']
            minor_planet.inclination_degrees = mpc_mp['inclination_degrees']
            minor_planet.eccentricity = mpc_mp['eccentricity']
            minor_planet.mean_daily_motion_degrees = mpc_mp['mean_daily_motion_degrees']
            minor_planet.semimajor_axis_au = mpc_mp['semimajor_axis_au']
            minor_planet.uncertainty = mpc_mp['uncertainty']
            minor_planet.reference = mpc_mp['reference']
            minor_planet.observations = mpc_mp['observations']
            minor_planet.oppositions = mpc_mp['oppositions']
            minor_planet.observation_period = mpc_mp['observation_period']
            minor_planet.rms_residual_arcseconds = mpc_mp['rms_residual_arcseconds']
            minor_planet.coarse_perturbers = mpc_mp['coarse_perturbers']
            minor_planet.precise_perturbers = mpc_mp['precise_perturbers']
            minor_planet.computer_name = mpc_mp['computer_name']
            minor_planet.hex_flags = mpc_mp['hex_flags']
            minor_planet.designation = mpc_mp['designation']
            minor_planet.last_observation_date = mpc_mp['last_observation_date']
            minor_planets.append(minor_planet)

    try:
        line_cnt = 1
        for minor_planet in minor_planets:
            progress(line_cnt, len(minor_planets), 'Importing minor planets')
            line_cnt += 1
            db.session.add(minor_planet)
        print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
