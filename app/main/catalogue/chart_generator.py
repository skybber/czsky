import subprocess
import os

def create_chart(dso_dname, full_file_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
    """View a deepsky object findchart."""
    prog_params = ['fchart3',
                   '-size', str(fld_size),
                   '-width', '220',
                   '-f', full_file_name,
                   '-capt', '',
                   '-limdso', str(dso_maglim),
                   '-limstar', str(star_maglim),
                   '-lstar', '0.06',
                   '-locl', '0.15',
                   '-ldso', '0.1',
                   '-llegend', '0.3',
                   '-usno-nomad', os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat'),
                   '-fmessier',
                   ]
    if night_mode:
        prog_params.append('-nm')
    if mirror_x:
        prog_params.append('-mx')
    if mirror_y:
        prog_params.append('-my')
    prog_params.append(dso_dname)
    p = subprocess.Popen(prog_params)
    p.wait()
