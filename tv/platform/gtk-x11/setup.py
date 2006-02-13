###############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.core import setup
from distutils.extension import Extension
from distutils.cmd import Command
import os
import sys
import shutil
import popen2
from Pyrex.Distutils import build_ext
from distutils import dep_util

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

def getConfigList(commandLine):
    """Get a list of directories from mozilla-config."""
    output = os.popen(commandLine, 'r').read().strip()
    return [i[2:] for i in output.split()]

mozilla_components = 'string dom gtkembedmoz necko xpcom'
mozilla_includes = getConfigList('mozilla-config --cflags %s' %
        mozilla_components)
mozilla_libs = getConfigList('mozilla-config --libs %s' % mozilla_components)

frontend_implementation_dir = os.path.join(root, 'platform', platform,
        'frontend_implementation')
xine_dir = os.path.join(root, 'platform', platform, 'xine')

def pkgconfigList(args):
    output = os.popen("pkg-config %s" % args).read()
    return output.strip().split(' ')

xinePackages = ['pygtk-2.0', 'gtk+-2.0', 'glib-2.0', 'gthread-2.0']

# Private extension modules to build.
ext_modules = [
    # Full-blown C++ extension modules.
    fasttypes_ext,

    # Pyrex sources.
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
    Extension("MozillaBrowser", [
            os.path.join(frontend_implementation_dir,'MozillaBrowser.pyx'),
            os.path.join(frontend_implementation_dir,'MozillaBrowserXPCOM.cc'),
            ],
              include_dirs=pygtk_includes + mozilla_includes,
              runtime_library_dirs=mozilla_libs,
              library_dirs=mozilla_libs,
              libraries=['gtk-x11-2.0', 'gtkembedmoz']),
    Extension('xine', [
        os.path.join(xine_dir, 'xine.pyx'),
        os.path.join(xine_dir, 'xine_impl.c'),
        ],
        libraries=['xine', 'X11'],
        include_dirs=['/usr/include/X11'],
        library_dirs=['/usr/X11R6/lib'],
        extra_compile_args=pkgconfigList("--cflags " + 
            ' '.join(xinePackages)),
        extra_link_args=pkgconfigList("--libs " + ' '.join(xinePackages)))
    ]


setup(
    console = ['DTV.py'],
    ext_modules = ext_modules,
    cmdclass = {'build_ext': build_ext}
)
