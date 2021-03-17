﻿"""BIM2SIM main module.

Usage:
    bim2sim project create <project_path> [-i <source>] [-s <target>] [-o]
    bim2sim project load [<project_path>]
    bim2sim --help
    bim2sim --version

Options:
    load                Load project from current working directory or given path
    create              Create project folder on given relative or absolute path
    -h --help           Show this screen.
    -v --version        Show version.
    -s <target> --sim <target>  Simulation to convert to.
    -i <source> --ifc <source>  Path to ifc file
    -o --open           Open config file
"""

import os
import sys

import docopt

from bim2sim import setup_default, Project, VERSION


def commandline_interface():
    """user interface"""

    args = docopt.docopt(__doc__, version=VERSION)

    # arguments
    project = args.get('project')
    load = args.get('load')
    create = args.get('create')

    path = args.get('<project_path>')
    target = args.get('--sim')
    source = args.get('--ifc')
    open_conf = args.get('--open')

    if project:
        setup_default(path)
        if create:
            pro = Project.create(path, source, target, open_conf)
        elif load:
            pro = Project(path)
        pro.run()
    else:
        print("Invalid arguments")
        exit()


def debug_params():
    """Set debug console arguments"""

    print("No parameters passed. Using debug parameters.")
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
    path_ifc = os.path.normcase(os.path.join(path_base, rel_example))

    #sys.argv.append('project')
    #sys.argv.append('create')
    #sys.argv.append(r'C:\temp\bim2sim\testproject')
    #sys.argv.extend(['-s', 'hkesim', '-i', path_ifc, '-o'])

    sys.argv.append('project')
    sys.argv.append('load')
    sys.argv.append(r'C:\temp\bim2sim\testproject')

    print("Debug parameters:\n%s"%("\n".join(sys.argv[1:])))


if len(sys.argv) <= 1:
    debug_params()

commandline_interface()
