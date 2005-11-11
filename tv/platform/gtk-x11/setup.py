###############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python-gcc-mt-1_33'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.core import setup
from distutils.extension import Extension
import os
import sys
import shutil
import popen2
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'gtk-x11'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')

root = os.path.normpath(root)
sys.path[0:0] = [
    os.path.join(root, 'platform', platform),
    os.path.join(root, 'platform'),
    os.path.join(root, 'portable'),
]

#### The fasttypes extension ####

fasttypes_ext = \
    Extension("fasttypes", 
        sources = [os.path.join(root, 'portable', 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )

(stdout, stdin) = popen2.popen2("pkg-config --cflags-only-I gtk+-2.0 glib-2.0 pygtk-2.0")
pygtk_includes = stdout.read().split(' -I')
pygtk_includes[0] = pygtk_includes[0][2:]
pygtk_includes[-1] = pygtk_includes[-1].strip()

# Private extension modules to build.
ext_modules = [
    # Full-blown C++ extension modules.
    fasttypes_ext,

    # Pyrex sources.
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
    Extension("HTMLDisplay", [os.path.join(root, 'platform', platform, 'frontend_implementation','HTMLDisplay.pyx')],
              include_dirs=pygtk_includes,
              libraries=['gtk-x11-2.0']),
]

setup(
    console = ['DTV.py'],
    ext_modules = ext_modules,
    cmdclass = {'build_ext': build_ext}
)
