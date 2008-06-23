# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import os.path
import os
import time
import socket
import copy
import sys
import string
import subprocess
import zipfile as zip
from glob import glob, iglob
from xml.sax.saxutils import escape
from distutils import sysconfig 
import distutils.command.install_data
import distutils.command.build_py

###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# The location of the NSIS compiler
NSIS_PATH = 'C:\\Program Files\\NSIS\\makensis.exe'

# If you're using the prebuilt DTV Dependencies Binary Kit, just set
# the path to it here, and ignore everything after this point. In
# fact, if you unpacked or checked out the binary kit in the same
# directory as DTV itself, the default value here will work.
#
# Otherwise, if you build the dependencies yourself instead of using
# the Binary Kit, ignore this setting and change all of the settings
# below.
defaultBinaryKitRoot = os.path.join(os.path.dirname(sys.argv[0]), \
                                    '..', '..', '..', 'dtv-binary-kit')
BINARY_KIT_ROOT = os.path.abspath(defaultBinaryKitRoot)

BOOST_ROOT = os.path.join(BINARY_KIT_ROOT, 'boost', 'win32')
BOOST_LIB_PATH = os.path.join(BOOST_ROOT, 'lib')
BOOST_INCLUDE_PATH = os.path.join(BOOST_ROOT, 'include')
BOOST_LIBRARIES = [os.path.splitext(os.path.basename(f))[0] for f in
        glob(os.path.join(BOOST_LIB_PATH, '*.lib'))]

ZLIB_INCLUDE_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib', 'include')
ZLIB_LIB_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib', 'lib')
ZLIB_RUNTIME_LIBRARY_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib')

OPENSSL_INCLUDE_PATH = os.path.join(BINARY_KIT_ROOT, 'openssl', 'include')
OPENSSL_LIB_PATH = os.path.join(BINARY_KIT_ROOT, 'openssl', 'lib')
OPENSSL_LIBRARIES = [ 'ssleay32', 'libeay32']

GTK_ROOT_PATH = os.path.join(BINARY_KIT_ROOT, 'gtk+-2.12.9-bundle')
GTK_INCLUDE_PATH = os.path.join(GTK_ROOT_PATH, 'include')
GTK_LIB_PATH = os.path.join(GTK_ROOT_PATH, 'lib')
GTK_RUNTIME_LIBRARY_PATH = os.path.join(GTK_ROOT_PATH, 'bin')

# Path to the Mozilla "xulrunner-sdk" distribution. We include a build in
# the Binary Kit to save you a minute or two, but if you want to be
# more up-to-date, nightlies are available from Mozilla at:
# http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-trunk/
XULRUNNER_SDK_PATH = os.path.join(BINARY_KIT_ROOT, 'xulrunner-sdk')
XULRUNNER_SDK_BIN_PATH = os.path.join(XULRUNNER_SDK_PATH, 'bin')

# Path to a build of the convert utility from imagemagick
IMAGEMAGICK_DIR = os.path.join(BINARY_KIT_ROOT, 'imagemagick')

def find_data_files(dest_path_base, source_path):
    retval = []
    for path, dirs, files in os.walk(source_path):
        if not path.startswith(source_path):
            raise AssertionError()
        dest_path = path.replace(source_path, dest_path_base)
        source_files = [os.path.join(path, f) for f in files]
        retval.append((dest_path, source_files))
        if '.svn' in dirs:
            dirs.remove('.svn')
    return retval

# Path to a build of the convert utility from imagemagick
IMAGEMAGICK_DIR = os.path.join(BINARY_KIT_ROOT, 'imagemagick')

# Name of python binary, so we can build the download daemon in
# another process. (Can we get this from Python itself?)
PYTHON_BINARY="python"

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.core import setup
from distutils.extension import Extension
from distutils.core import Command
from distutils import log
import py2exe
import os
import sys
import shutil
import re
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'windows-xul'

# Find the top of the source tree and set search path
root_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
root_dir = os.path.normpath(os.path.abspath(root_dir))
platform_dir = os.path.join(root_dir, 'platform', 'windows-xul', 'plat')
widgets_dir = os.path.join(platform_dir, 'frontends', 'widgets')
portable_dir = os.path.join(root_dir, 'portable')
resources_dir = os.path.join(root_dir, 'resources')
sys.path.insert(0, root_dir)
# when we install the portable modules, they will be in the miro package, but
# at this point, they are in a package named "portable", so let's hack it
import portable
sys.modules['miro'] = portable

from miro import util

#### Extensions ####

database_ext = Extension("miro.database", 
        sources=[os.path.join(root_dir, 'portable', 'database.pyx')])

sorts_ext = Extension("miro.sorts", 
        sources=[os.path.join(root_dir, 'portable', 'sorts.pyx')])

fasttypes_ext = \
    Extension("miro.fasttypes", 
        sources = [os.path.join(root_dir, 'portable', 'fasttypes.cpp')],
        library_dirs = [BOOST_LIB_PATH],
        include_dirs = [BOOST_INCLUDE_PATH]
    )

xulrunnerbrowser_ext_dir = os.path.join(widgets_dir, 'XULRunnerBrowser')
xulrunnerbrowser_ext = Extension("miro.plat.frontends.widgets.xulrunnerbrowser",
        include_dirs=[
            os.path.join(XULRUNNER_SDK_PATH, 'sdk', 'include'),
            os.path.join(XULRUNNER_SDK_PATH, 'include'),
            os.path.join(GTK_INCLUDE_PATH, 'atk-1.0'),
            os.path.join(GTK_INCLUDE_PATH, 'gtk-2.0'),
            os.path.join(GTK_INCLUDE_PATH, 'glib-2.0'),
            os.path.join(GTK_INCLUDE_PATH, 'glib-2.0'),
            os.path.join(GTK_INCLUDE_PATH, 'pango-1.0'),
            os.path.join(GTK_INCLUDE_PATH, 'cairo'),
            os.path.join(GTK_LIB_PATH, 'glib-2.0', 'include'),
            os.path.join(GTK_LIB_PATH, 'gtk-2.0', 'include'),
        ],
        define_macros=[
            ("XP_WIN", 1), 
            ("XPCOM_GLUE", 1),
        ],
        library_dirs=[
            os.path.join(XULRUNNER_SDK_PATH, 'lib'),
            GTK_LIB_PATH,
        ],
        libraries=[
            'xpcomglue',
            'xul',
            'user32',
            'gdk-win32-2.0',
            'gtk-win32-2.0',
        ],
        language="c++",
        sources = [
            os.path.join(xulrunnerbrowser_ext_dir, 'xulrunnerbrowser.pyx'),
            os.path.join(xulrunnerbrowser_ext_dir, 'MiroBrowserEmbed.cpp'),
            os.path.join(xulrunnerbrowser_ext_dir, 'FixFocus.cpp'),
            os.path.join(xulrunnerbrowser_ext_dir, 'Init.cpp'),
            ]
        )

# Setting the path here allows py2exe to find the DLLS
os.environ['PATH'] = ';'.join([
    os.environ['PATH'], BOOST_LIB_PATH, ZLIB_RUNTIME_LIBRARY_PATH,
    OPENSSL_LIB_PATH, GTK_RUNTIME_LIBRARY_PATH ])

##### The libtorrent extension ####

def fetchCpp():
    for root,dirs,files in os.walk(os.path.join(portable_dir, 'libtorrent')):
        if '.svn' in dirs:
            dirs.remove('.svn')
        if '_svn' in dirs:
            dirs.remove('_svn')
        for file in files:
            if file.endswith('.cpp'):
                yield os.path.join(root,file)

libtorrent_sources=list(fetchCpp())
libtorrent_sources.remove(os.path.join(portable_dir, 'libtorrent\\src\\file.cpp'))

libtorrent_ext = Extension(
        "miro.libtorrent", 
        include_dirs = [
            os.path.join(portable_dir, 'libtorrent', 'include'),
            os.path.join(portable_dir, 'libtorrent', 'include', 'libtorrent'),
            BOOST_INCLUDE_PATH, 
            ZLIB_INCLUDE_PATH, 
            OPENSSL_INCLUDE_PATH,
        ],
        library_dirs = [ BOOST_LIB_PATH, OPENSSL_LIB_PATH, ZLIB_LIB_PATH],
        libraries = OPENSSL_LIBRARIES + BOOST_LIBRARIES + [
            'wsock32', 'gdi32', 'ws2_32', 'zdll'
            ],
        extra_compile_args = [  '-DBOOST_WINDOWS',
            '-DWIN32_LEAN_AND_MEAN',
            '-D_WIN32_WINNT=0x0500',
            '-D__USE_W32_SOCKETS',
            '-D_WIN32',
            '-DWIN32',
            '-DBOOST_ALL_NO_LIB',
            '-D_FILE_OFFSET_BITS=64',
            '-DBOOST_THREAD_USE_LIB',
            '-DTORRENT_USE_OPENSSL=1',
            '-DNDEBUG=1',
            '/EHa', '/GR',
            ],
        sources = libtorrent_sources)

# Private extension modules to build.
ext_modules = [
    fasttypes_ext,
    database_ext,
    sorts_ext,
    libtorrent_ext,
    xulrunnerbrowser_ext,
]

def fillTemplate(templatepath, outpath, **vars):
    s = open(templatepath, 'rt').read()
    s = string.Template(s).safe_substitute(**vars)
    f = open(outpath, "wt")
    f.write(s)
    f.close()

# Data files
data_files = []
data_files.extend(find_data_files('xulrunner', XULRUNNER_SDK_BIN_PATH))
data_files.extend(find_data_files('imagemagick', IMAGEMAGICK_DIR))
image_loader_path = os.path.join('lib', 'gtk-2.0', '2.10.0', 'loaders')
data_files.extend(find_data_files(image_loader_path, 
    os.path.join(GTK_ROOT_PATH, image_loader_path)))

# handle the resources subdirectories.
for dir in ('searchengines', 'wimages'):
    dest_dir = os.path.join('resources', dir)
    source_dir = os.path.join(resources_dir, dir)
    data_files.extend(find_data_files(dest_dir, source_dir))

###############################################################################

#### Our specialized build_py command ####
class build_py (distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the miro
    package.
    """

    def expand_templates(self):
        app_config = os.path.join(resources_dir, 'app.config.template')
        conf = util.readSimpleConfigFile(app_config)
        for path in [os.path.join(portable_dir,'dl_daemon','daemon.py')]:
            template = string.Template(open(path+".template", 'rt').read())
            fout = open(path, 'wt')
            fout.write(template.substitute(**conf))
        
    def run (self):
        """Extend build_py's module list to include the miro modules."""
        self.expand_templates()
        return distutils.command.build_py.build_py.run(self)


#### Our specialized install_data command ####
class install_data (distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        template = os.path.join(resources_dir, 'app.config.template')
        dest = os.path.join(self.install_dir, 'resources', 'app.config')
        revision = util.queryRevision(root_dir)
        if revision is None:
            revision = "unknown"
            revisionurl = "unknown"
            revisionnum = "unknown"
        else:
            revisionurl = revision[0]
            revisionnum = revision[1]
            revision = "%s - %s" % revision

        self.mkpath(os.path.dirname(dest))
        # We don't use the dist utils copy_file() because it only copies
        # the file if the timestamp is newer
        fillTemplate(template, dest,
            APP_REVISION=revision,
            APP_REVISION_NUM=revisionnum,
            APP_REVISION_URL=revisionurl,
            APP_PLATFORM='gtk-x11',
            BUILD_MACHINE="%s@%s" % (os.environ['username'],
                socket.gethostname()),
            BUILD_TIME=str(time.time()))
        self.outfiles.append(dest)

    def install_gdk_pixbuf_loaders(self):
        basename = os.path.join('etc', 'gtk-2.0', 'gdk-pixbuf.loaders')
        source = os.path.join(GTK_ROOT_PATH, basename)
        dest = os.path.join(self.install_dir, basename)
        contents = open(source).read()
        # Not sure why they have paths like this in the file, but we need to
        # change them.
        contents = contents.replace("c:/devel/target/9c384abfa28a3e070eb60fc2972f823b/",
                "")
        self.mkpath(os.path.dirname(dest))
        open(dest, 'wt').write(contents)
        self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()
        self.install_gdk_pixbuf_loaders()

if __name__ == "__main__":
    setup(
        console=['Miro.py', 'Miro_Downloader.py'],
        ext_modules = ext_modules,
        packages = [
            'miro',
            'miro.dl_daemon',
            'miro.dl_daemon.private',
            'miro.frontends',
            'miro.frontends.widgets',
            'miro.frontends.widgets.gtk',
            'miro.plat',
            'miro.plat.frontends',
            'miro.plat.frontends.widgets',
        ],
        package_dir = {
            'miro': portable_dir,
            'miro.plat': platform_dir,
        },
        data_files = data_files,
        cmdclass = {
            'build_py': build_py,
            'build_ext': build_ext,
            'install_data': install_data,
        },
        options = {
            'py2exe': {
                'packages' : [
                    'encodings',
                    ],
                'includes': 'cairo, pango, pangocairo, atk, gobject',
            },
        },
    )
