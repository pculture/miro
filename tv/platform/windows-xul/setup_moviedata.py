import os
import sys
import setup as core_setup
from distutils.core import setup
import py2exe

# The name of this platform.
platform = 'windows-xul'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
root = os.path.normpath(root)
sys.path.insert(0, os.path.join(root, 'portable'))

import util

templateVars = util.readSimpleConfigFile(os.path.join(root, 'resources', 'app.config'))

script_path = os.path.join(os.path.dirname(__file__), 'moviedata_util.py')

setup(
    console=[{"dest_base":("%s_MovieData"%templateVars['shortAppName']),"script":script_path}],
    zipfile=None,
)
