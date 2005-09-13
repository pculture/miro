from distutils.core import setup
from distutils.extension import Extension
import py2exe
import os
import sys
import shutil
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'windows'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0] = [
    os.path.join(root, 'platform', platform),
    os.path.join(root, 'platform'),
    os.path.join(root, 'portable'),
]

# Only now may we import things from our own tree
#import vlchelper.info

py2exe_options = {
    # Prevents "LookupError: unknown encoding: idna"
    'packages': "encodings"
}

WebBrowser_ext = Extension('WebBrowser',
                           sources = ['WebBrowser.cpp'],
                           libraries = ['gdi32', 'shell32', 'user32',
                                        'advapi32'],
                          )

# Private extension modules to build.
ext_modules = [
    #vlchelper.info.getExtension(root),
    WebBrowser_ext,
    # Pyrex sources.
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
]

setup(
    console = ['DTV.py'],
    ext_modules = ext_modules,
    options=dict(
        py2exe=py2exe_options,
    ),
    cmdclass = {'build_ext': build_ext}
)

# Brutal hacks to set up the distribution environment.
if 'py2exe' in sys.argv:
    # NEEDS: Try to figure out the root distribution directory. Ugly.
    distRoot = 'dist'
    for i in range(0,len(sys.argv)-1):
	if sys.argv[i] == '--dist-dir' or sys.argv[i] == '-d':
	    distRoot = sys.argv[i+1]

    # Copy our resources into the dist dir the way we like them.
    resourceRoot = os.path.join(root, 'resources')
    resourceTarget = os.path.join(distRoot, 'resources')
    print 'Removing old %s if any' % resourceRoot
    shutil.rmtree(resourceTarget, True)
    print 'Populating %s' % resourceTarget
    shutil.copytree(resourceRoot, resourceTarget)
