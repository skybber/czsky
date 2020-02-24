#!/bin/bash
import glob, os
from shutil import copyfile
from app.commons.dso_utils import normalize_dso_name

prefixes = ('NGC', 'UGC', 'M', 'Abell', 'Sh2-', 'PGC', 'IC', 'HCG')

def _try_copy(f, appendix, img_dst_dir):
    if _has_known_prefix(f) and f.endswith(appendix):
        base_name = os.path.basename(f)[:-len(appendix)]
        idx = base_name.find('_')
        if idx >= 0:
            base_name = base_name[:idx]
        dso_file_name = normalize_dso_name(base_name)
        copyfile(f, os.path.join(img_dst_dir, dso_file_name + '.jpg'))
        return True
    return False

def _has_known_prefix(f):
    base_name = os.path.basename(f)
    return base_name.startswith(prefixes)

def normalize_glahn_img(img_src_dir, img_dst_dir):
    files = [f for f in sorted(glob.glob(img_src_dir + '/*.jpg'))]
    ignore_set = set()
    for f in files:
        if _try_copy(f, '_8.jpg', img_dst_dir):
            ignore_set.add(f)
            ignore_set.add(f[:-len('_8.jpg')] + '.jpg')

    for f in files:
        if _try_copy(f, '_14.jpg', img_dst_dir):
            ignore_set.add(f)
            ignore_set.add(f[:-len('_14.jpg')] + '.jpg')

    for f in files:
        if _try_copy(f, '_27.jpg', img_dst_dir):
            ignore_set.add(f)
            ignore_set.add(f[:-len('_27.jpg')] + '.jpg')

    for f in files:
        if _try_copy(f, '-Gruppe.jpg', img_dst_dir):
            ignore_set.add(f)

    for f in files:
        if not f in ignore_set and _has_known_prefix(f):
            base_name = os.path.basename(f)
            idx = base_name.find('_')
            if idx >= 0:
                if _try_copy(f, base_name[idx:], img_dst_dir):
                    ignore_set.add(f)
    for f in files:
        if not f in ignore_set and _has_known_prefix(f):
            base_name = os.path.basename(f)
            if base_name.endswith('.jpg'):
                dso_name = base_name[:-len('.jpg')]
                dso_file_name = normalize_dso_name(dso_name) + '.jpg'
                copyfile(f, os.path.join(img_dst_dir, dso_file_name))
