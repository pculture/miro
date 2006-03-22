##############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from glob import glob
import os
from distutils.core import setup
from distutils.extension import Extension

from Pyrex.Distutils import build_ext

from paths import *
import util
from build_py import build_py
from install_data import install_data
from bdist_deb import bdist_deb

#### The fasttypes extension ####
fasttypes_ext = \
    Extension("democracy.fasttypes", 
        sources = [os.path.join(portable_dir, 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )
#### MozillaBrowser Extension ####
mozilla_browser_options = util.parsePkgConfig("pkg-config" , 
        "gtk+-2.0 glib-2.0 pygtk-2.0")
util.parsePkgConfig("mozilla-config", 
        "string dom gtkembedmoz necko xpcom", mozilla_browser_options)
# mozilla-config doesn't get gtkembedmoz one for some reason
mozilla_browser_options['libraries'].append('gtkembedmoz') 
mozilla_browser_ext = Extension("democracy.MozillaBrowser",
        [ os.path.join(frontend_implementation_dir,'MozillaBrowser.pyx'),
          os.path.join(frontend_implementation_dir,'MozillaBrowserXPCOM.cc'),
        ],
        runtime_library_dirs=['/usr/lib/mozilla'],
        **mozilla_browser_options)
#### Xine Extension ####
xine_options = util.parsePkgConfig('pkg-config', 
        'libxine pygtk-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
xine_ext = Extension('democracy.xine', [
        os.path.join(xine_dir, 'xine.pyx'),
        os.path.join(xine_dir, 'xine_impl.c'),
        ], **xine_options)
#### Build the data_files list ####
def listfiles(path):
    return [f for f in glob(os.path.join(path, '*')) if os.path.isfile(f)]
data_files = []
# append the root resource directory.
# filter out app.config.template (which is handled specially)
# add democracy.glade
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
files.append(os.path.join(platform_dir, 'glade', 'democracy.glade'))
data_files.append(('/usr/share/democracy/resources/', files))
# handle the sub directories.
for dir in ('templates', 'css', 'images'):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/democracy/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))
#### Run setup ####
setup(name='democracy', 
    version='0.8', 
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getdemocracy.com/',
    download_url='http://www.getdemocracy.com/downloads/',
    scripts=[os.path.join(platform_dir, 'democracyplayer')],
    data_files=data_files,
    ext_modules = [
        fasttypes_ext, mozilla_browser_ext, xine_ext,
        Extension("democracy.database", 
                [os.path.join(portable_dir, 'database.pyx')]),
        Extension("democracy.template", 
                [os.path.join(portable_dir, 'template.pyx')]),
    ],
    packages = [
        'democracy.frontend_implementation',
        'democracy.BitTorrent',
        'democracy.dl_daemon',
        'democracy.dl_daemon.private',
    ],
    package_dir = {
        'democracy.frontend_implementation' : frontend_implementation_dir,
        'democracy.BitTorrent' : bittorrent_dir,
        'democracy.dl_daemon' : dl_daemon_dir,
    },
    cmdclass = {
        'build_ext': build_ext, 
        'build_py': build_py,
        'bdist_deb': bdist_deb,
        'install_data': install_data,
    }
)
