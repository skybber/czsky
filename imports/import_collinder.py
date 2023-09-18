import re
import numpy as np

from app import db
from app.models.constellation import Constellation
from app.models.catalogue import Catalogue
from app.models.deepskyobject import DeepskyObject, IMPORT_SOURCE_COLLINDER

from .import_utils import progress

def import_collinder(collinder_data_file):
    """Import data from Collinder catalog."""
    from sqlalchemy.exc import IntegrityError

    constell_dict = {}

    for co in Constellation.query.all():
        constell_dict[co.iau_code.upper()] = co.id

    sf = open(collinder_data_file, 'r', encoding='utf-8')
    lines = sf.readlines()
    sf.close()

    line_cnt = 1
    total_lines = len(lines)

    cr_catalog_id = Catalogue.query.filter_by(code = 'Cr').first().id

    try:
        for line in lines[1:]:
            progress(line_cnt, total_lines, 'Reading Collinder catalogue')
            line_cnt += 1

            cr_num = int(line[0:3])
            
            cr_name = 'Cr{}'.format(cr_num)
            
            c = DeepskyObject.query.filter_by(name = cr_name).first()
            
            if c is None:
                c = DeepskyObject()
                c.import_source = IMPORT_SOURCE_COLLINDER
            else:
                if c.import_source != IMPORT_SOURCE_COLLINDER:
                    continue
                
            other_names = line[14:56].strip().split(',')
            
            master_object = None
            for other_name in other_names:
                if other_name.startswith('NGC') or other_name.startswith('IC'):
                    master_object = DeepskyObject.query.filter_by(name = other_name).first()
                    if master_object is not None:
                        break

            if master_object:
                master_id = master_object.id
                ra = master_object.ra
                dec = master_object.dec
                constellation_id = master_object.constellation_id
                mag = master_object.mag
                major_axis = master_object.major_axis
                minor_axis = master_object.minor_axis
                axis_ratio = master_object.axis_ratio
                position_angle = master_object.position_angle
                surface_bright = master_object.surface_bright
                common_name = master_object.common_name
                descr = master_object.descr
            else:
                continue # just dont import without existing NGC
                master_id = None
                ra = float(line[67:69])*np.pi/12.0 + float(line[71:73])*np.pi/(12.0*60.0) + float(line[75:79])*np.pi/(12*60.0*60)
                dec = float(line[84]+'1')*(float(line[85:87])*np.pi/180.0 + float(line[89:91])*np.pi/(180.0*60) + float(line[93:95])*np.pi/(180.0*60*60))
                constellation_id = constell_dict[line[56:59].upper()]
                strmag = line[101:112].strip()
                match_mag = re.match('.+([0-9])[^0-9]*$', strmag)
                if match_mag is not None:
                    mag = float(strmag[:match_mag.start(1) + 1])
                else:
                    mag = None
                obj_size = line[123:134].strip().split('x')
                major_axis = None
                minor_axis = None
                axis_ratio = None
                if len(obj_size) == 1:
                    try:
                        major_axis = 60 * float(obj_size[0])
                        axis_ratio = 1
                    except ValueError:
                        pass
                elif len(obj_size) == 2:
                    major_axis = 60 * float(obj_size[0])
                    minor_axis = 60 * float(obj_size[1])
                    axis_ratio = minor_axis / major_axis
                position_angle = None
                surface_bright = 100
                common_name = None
                descr = None

            c.master_id = master_id
            c.name = cr_name
            c.type = 'OC'
            c.subtype = None
            c.ra = ra
            c.dec = dec
            c.constellation_id = constellation_id
            c.catalogue_id = cr_catalog_id
            c.major_axis = major_axis
            c.minor_axis = minor_axis
            c.axis_ratio = axis_ratio
            c.position_angle = position_angle
            c.mag = mag
            c.surface_bright = surface_bright
            c.hubble_type = None
            c.c_star_u_mag = None
            c.c_star_b_mag = None
            c.c_star_v_mag = None
            c.common_name = common_name
            c.descr = descr
            db.session.add(c)
        db.session.commit()
    except KeyError as err:
        print('\nKey error: {}'.format(err))
        db.session.rollback()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()
    print('') # finish on new line
