#!/usr/bin/python

import sys, re, getopt, os, glob

def checkdir(dir, param):
    if not os.path.exists(dir) or not os.path.isdir(dir):
        print('error: -' + param + ': existing directory expected.')
        usage()
        return False;
    return True

def usage():
    print('Usage : rename_8mag_files.py --path path_to_8mag_dir --debug')

def main():
    path = None
    debug_log = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['path=', 'debug'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, a in opts:
        if o == '--path':
            path = a
        elif o == '--debug':
            debug_log = True

    if path is None:
        usage()
        sys.exit(2)

    if not checkdir(path, 'src_path'):
        sys.exit(2)

    files = [f for f in glob.glob(path + "**/*.php")]
    for f in files:
        if '(' in f or ')' in f:
            new_name = f.replace('(', '_').replace(')', '_')
            print('Ranaming ' + f + ' to ' + new_name)
            os.rename(f, new_name)

    print('Done.')

main()