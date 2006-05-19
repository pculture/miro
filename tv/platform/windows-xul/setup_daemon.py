import os
import sys
from distutils.core import setup
from distutils.extension import Extension
import py2exe
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'windows-xul'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0] = [
    os.path.join(root, 'portable', 'dl_daemon'),

    # The daemon's "platform" files are in the private directory
    os.path.join(root, 'portable', 'dl_daemon','private'),
    os.path.join(root, 'portable'),
]
root = os.path.normpath(root)
ext_modules=[
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
]

setup(
    console=[os.path.join(root, 'portable', 'dl_daemon', 'Democracy_Downloader.py')],
    ext_modules=ext_modules,
    zipfile=None,
    cmdclass = {
	'build_ext': build_ext,
    }
)
