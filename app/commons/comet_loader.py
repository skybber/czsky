from sqlalchemy.exc import IntegrityError
import numpy as np

from skyfield.api import load
from skyfield.data import mpc


from app import db
from app.models import Comet
from imports.import_utils import progress

# comets intended to be periodically updated, so it is not part of import package


def load_all_mpc_comets():
    with load.open(mpc.COMET_URL, reload=True) as f:
        all_mpc_comets = mpc.load_comets_dataframe_slow(f)
        all_mpc_comets = (all_mpc_comets.sort_values('reference')
                          .groupby('designation', as_index=False).last()
                          .set_index('designation', drop=False))
        all_mpc_comets['comet_id'] = np.where(all_mpc_comets['designation_packed'].isnull(), all_mpc_comets['designation'], all_mpc_comets['designation_packed'])
        all_mpc_comets['comet_id'] = all_mpc_comets['comet_id'].str.replace('/','')
        all_mpc_comets['comet_id'] = all_mpc_comets['comet_id'].str.replace(' ', '')
        return all_mpc_comets


def import_update_comets(all_mpc_comets, show_progress=False):
    comets = []
    for index, mpc_comet in all_mpc_comets.iterrows():
        comet_id = mpc_comet['comet_id']
        
        comet = Comet.query.filter_by(comet_id=comet_id).first()
        if comet is None:
            comet = Comet()
            comet.comet_id = comet_id
            
        comet.designation = mpc_comet['designation']
        comet.number = mpc_comet['number']
        comet.orbit_type = mpc_comet['orbit_type']
        comet.designation_packed = mpc_comet['designation_packed']
        comet.perihelion_year = mpc_comet['perihelion_year']
        comet.perihelion_month = mpc_comet['perihelion_month']
        comet.perihelion_day = mpc_comet['perihelion_day']
        comet.perihelion_distance_au = mpc_comet['perihelion_distance_au']
        comet.eccentricity = mpc_comet['eccentricity']
        comet.argument_of_perihelion_degrees = mpc_comet['argument_of_perihelion_degrees']
        comet.longitude_of_ascending_node_degrees = mpc_comet['longitude_of_ascending_node_degrees']
        comet.inclination_degrees = mpc_comet['inclination_degrees']
        comet.perturbed_epoch_year = mpc_comet['perturbed_epoch_year']
        comet.perturbed_epoch_month = mpc_comet['perturbed_epoch_month']
        comet.perturbed_epoch_day = mpc_comet['perturbed_epoch_day']
        comet.magnitude_g = mpc_comet['magnitude_g']
        comet.magnitude_k = mpc_comet['magnitude_k']
        comet.reference = mpc_comet['reference']
        comets.append(comet)
    try:
        line_cnt = 1
        for comet in comets:
            if show_progress:
                progress(line_cnt, len(comets), 'Importing minor planets')
            line_cnt += 1
            db.session.add(comet)
        if show_progress:
            print('')
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()