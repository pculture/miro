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
from distutils.core import Command
import distutils.command.install_data
import distutils.command.build_py
from distutils.ccompiler import new_compiler

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
GTK_BIN_PATH = os.path.join(GTK_ROOT_PATH, 'bin')
GTK_INCLUDE_DIRS = [
        os.path.join(GTK_INCLUDE_PATH, 'atk-1.0'),
        os.path.join(GTK_INCLUDE_PATH, 'gtk-2.0'),
        os.path.join(GTK_INCLUDE_PATH, 'glib-2.0'),
        os.path.join(GTK_INCLUDE_PATH, 'glib-2.0'),
        os.path.join(GTK_INCLUDE_PATH, 'pango-1.0'),
        os.path.join(GTK_INCLUDE_PATH, 'cairo'),
        os.path.join(GTK_LIB_PATH, 'glib-2.0', 'include'),
        os.path.join(GTK_LIB_PATH, 'gtk-2.0', 'include'),
]

PYGOBJECT_INCLUDE_DIR = os.path.join(BINARY_KIT_ROOT, 'pygobject')

# Path to the Mozilla "xulrunner-sdk" distribution. We include a build in
# the Binary Kit to save you a minute or two, but if you want to be
# more up-to-date, nightlies are available from Mozilla at:
# http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-trunk/
XULRUNNER_SDK_PATH = os.path.join(BINARY_KIT_ROOT, 'xulrunner-sdk')
XULRUNNER_SDK_BIN_PATH = os.path.join(XULRUNNER_SDK_PATH, 'bin')

VLC_PATH = os.path.join(BINARY_KIT_ROOT, 'libvlc')

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
import py2exe.build_exe
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
platform_dir = os.path.join(root_dir, 'platform', 'windows-xul')
platform_package_dir = os.path.join(platform_dir, 'plat')
widgets_dir = os.path.join(platform_package_dir, 'frontends', 'widgets')
portable_dir = os.path.join(root_dir, 'portable')
portable_widgets_dir = os.path.join(portable_dir, 'frontends', 'widgets')
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

pygtkhacks_ext = Extension("miro.frontends.widgets.gtk.pygtkhacks",
        sources = [
            os.path.join(portable_widgets_dir, 'gtk', 'pygtkhacks.pyx'),
        ],
        include_dirs=GTK_INCLUDE_DIRS + [PYGOBJECT_INCLUDE_DIR],
        library_dirs=[GTK_LIB_PATH],
        libraries=[
            'gtk-win32-2.0',
        ])

xulrunnerbrowser_ext_dir = os.path.join(widgets_dir, 'XULRunnerBrowser')
xulrunnerbrowser_ext = Extension("miro.plat.frontends.widgets.xulrunnerbrowser",
        include_dirs=[
            os.path.join(XULRUNNER_SDK_PATH, 'sdk', 'include'),
            os.path.join(XULRUNNER_SDK_PATH, 'include'),
        ] + GTK_INCLUDE_DIRS,
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
    OPENSSL_LIB_PATH, GTK_BIN_PATH ])

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
    pygtkhacks_ext,
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
data_files.append(('', iglob(os.path.join(GTK_BIN_PATH, '*.dll'))))
data_files.extend(find_data_files('vlc-plugins', 
    os.path.join(VLC_PATH, 'vlc-plugins')))
data_files.append(('', [os.path.join(VLC_PATH, 'libvlc.dll')]))
data_files.append(('', [os.path.join(VLC_PATH, 'libvlccore.dll')]))

# handle the resources subdirectories.
for dir in ('searchengines', 'wimages'):
    dest_dir = os.path.join('resources', dir)
    source_dir = os.path.join(resources_dir, dir)
    data_files.extend(find_data_files(dest_dir, source_dir))

def get_template_variables():
    app_config = os.path.join(resources_dir, 'app.config.template')
    return util.read_simple_config_file(app_config)

###############################################################################

#### Our specialized build_py command ####
class build_py (distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the miro
    package.
    """

    def expand_templates(self):
        conf = get_template_variables()
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
        revision = util.query_revision(root_dir)
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
            APP_PLATFORM='windows-xul',
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

# We want to make sure we include msvcp71.dll in the dist directory.
# Recipe taken from
# http://www.py2exe.org/index.cgi/OverridingCriteraForIncludingDlls
DLLS_TO_INCLUDE = [
        'msvcp71.dll',
]
origIsSystemDLL = py2exe.build_exe.isSystemDLL
def isSystemDLL(pathname):
    if os.path.basename(pathname).lower() in DLLS_TO_INCLUDE:
        return False
    else:
        return origIsSystemDLL(pathname)
py2exe.build_exe.isSystemDLL = isSystemDLL

class build_movie_data_util(Command):
    description = "build the Miro Movie Data Utility"

    user_options = [
            ('build-dir=', 'd', "directory to build to"),
    ]


    def initialize_options(self):
        self.build_dir = None

    def finalize_options(self):
        if self.build_dir == None:
            build = self.distribution.get_command_obj('build')
            self.build_dir = os.path.join(build.build_base, 'moviedata_util')

    def run(self):
        log.info("building movie data utility")

        sources = [ os.path.join(platform_dir, 'moviedata_util.c') ]
        python_base = sysconfig.get_config_var('prefix')
        include_dirs = [ sysconfig.get_python_inc() ]
        library_dirs = [ os.path.join(python_base, 'libs')]

        compiler = new_compiler( verbose=self.verbose, dry_run=self.dry_run,
                force=self.force)
        sysconfig.customize_compiler(compiler)
        objects = compiler.compile(sources, output_dir=self.build_dir,
                include_dirs=include_dirs)

        compiler.link_executable(objects, 'Miro_MovieData',
                library_dirs=library_dirs, output_dir=self.build_dir)


class bdist_miro(Command):
    description = "Build Miro"

    user_options = [ ]

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('py2exe')
        self.run_command('build_movie_data_util')
        self.copy_movie_data_util()

    def copy_movie_data_util(self):
        dist_dir = self.get_finalized_command('py2exe').dist_dir
        build_cmd = self.distribution.get_command_obj('build_movie_data_util')
        build_cmd.build_dir

        self.copy_file(os.path.join(build_cmd.build_dir, 'Miro_MovieData.exe'),
            dist_dir)
        self.copy_file(os.path.join(platform_dir, "moviedata_util.py"),
                dist_dir)

class runmiro (Command):
    description = "build Miro and start it up"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


    def run(self):
        self.run_command('bdist_miro')
        olddir = os.getcwd()
        os.chdir(self.get_finalized_command('py2exe').dist_dir)
        os.system("Miro.exe")
        os.chdir(olddir)

class bdist_nsis (Command):
    description = "create Miro installer using NSIS"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


    def run(self):
        self.run_command('bdist_miro')
        self.dist_dir = self.get_finalized_command('py2exe').dist_dir


        log.info("building installer")

        template_vars = get_template_variables()

        self.copy_file(os.path.join(platform_dir, 'Miro.nsi'), self.dist_dir)
        self.copy_file("Miro.ico", os.path.join(self.dist_dir, "%s.ico" %
            template_vars['shortAppName']))
        self.copy_file("iHeartMiro-installer-page.ini", self.dist_dir)
        self.copy_file("miro-installer.ico", self.dist_dir)
        self.copy_file("miro-install-image.bmp", self.dist_dir)

        nsisVars = {}
        for (ourName, nsisName) in [
            ('appVersion', 'CONFIG_VERSION'),
            ('projectURL', 'CONFIG_PROJECT_URL'),
            ('shortAppName', 'CONFIG_SHORT_APP_NAME'),
            ('longAppName', 'CONFIG_LONG_APP_NAME'),
            ('publisher', 'CONFIG_PUBLISHER'),
            ]:
            nsisVars[nsisName] = template_vars[ourName]

        nsisVars['CONFIG_EXECUTABLE'] = "%s.exe" % template_vars['shortAppName']
        nsisVars['CONFIG_DOWNLOADER_EXECUTABLE'] = "%s_Downloader.exe" % \
                template_vars['shortAppName']
        nsisVars['CONFIG_MOVIE_DATA_EXECUTABLE'] = "%s_MovieData.exe" % \
                template_vars['shortAppName']
        nsisVars['CONFIG_ICON'] = "%s.ico" % template_vars['shortAppName']
        nsisVars['CONFIG_PROG_ID'] = template_vars['longAppName'].replace(" ",".")+".1"

        # One stage installer
        outputFile = "%s-%s.exe" % \
                (template_vars['shortAppName'], template_vars['appVersion'])
        nsisVars['CONFIG_OUTPUT_FILE'] = outputFile
        nsisVars['CONFIG_TWOSTAGE'] = "No"

        nsisArgs = ["/D%s=%s" % (k, v) for (k, v) in nsisVars.iteritems()]
        nsisArgs.append(os.path.join(self.dist_dir, "Miro.nsi"))

        if os.access(outputFile, os.F_OK):
            os.remove(outputFile)
        if subprocess.call([NSIS_PATH] + nsisArgs) != 0:
            print "ERROR creating the 1 stage installer, quitting"
            return

        # Two stage installer
        outputFile = "%s-%s-twostage.exe" % \
            ( template_vars['shortAppName'], template_vars['appVersion'] )
        nsisVars['CONFIG_OUTPUT_FILE'] = outputFile
        nsisVars['CONFIG_TWOSTAGE'] = "Yes"

        nsisArgs = ["/D%s=%s" % (k, v) for (k, v) in nsisVars.iteritems()]
        nsisArgs.append(os.path.join(self.dist_dir, "Miro.nsi"))

        if os.access(outputFile, os.F_OK):
            os.remove(outputFile)
        subprocess.call([NSIS_PATH] + nsisArgs)

        zip_path = os.path.join (self.dist_dir, "%s-Contents-%s.zip" %
            (template_vars['shortAppName'],template_vars['appVersion']))
        self.zipfile = zip.ZipFile(zip_path, 'w', zip.ZIP_DEFLATED)
        self.addFile (nsisVars['CONFIG_EXECUTABLE'])
        self.addFile (nsisVars['CONFIG_ICON'])
        self.addFile (nsisVars['CONFIG_MOVIE_DATA_EXECUTABLE'])
        self.addFile ("moviedata_util.py")
        self.addGlob ("*.dll")

        self.addDirectory ("defaults")
        self.addDirectory ("resources")
        self.addDirectory ("xulrunner")
        self.addDirectory ("imagemagick")

        self.zipfile.close()

    def addGlob(self, wildcard):
        wildcard = os.path.join (self.dist_dir, wildcard)
        length = len(self.dist_dir)
        for filename in iglob(wildcard):
            if filename[:length] == (self.dist_dir):
                filename = filename[length:]
                while len(filename) > 0 and (filename[0] == '/' or filename[0] == '\\'):
                    filename = filename[1:]
            print "Compressing %s" % (filename,)
            self.zipfile.write (os.path.join (self.dist_dir, filename), filename)

    def addFile(self, filename):
        length = len(self.dist_dir)
        if filename[:length] == (self.dist_dir):
            filename = filename[length:]
            while len(filename) > 0 and (filename[0] == '/' or filename[0] == '\\'):
                filename = filename[1:]
        print "Compressing %s" % (filename,)
        self.zipfile.write (os.path.join (self.dist_dir, filename), filename)

    def addDirectory (self, dirname):
        for root, dirs, files in os.walk (os.path.join (self.dist_dir, dirname)):
            for name in files:
                self.addFile (os.path.join (root, name))

if 0:
    class bdist_u3 (bdist_xul_dumb):
        def run(self):
            bdist_xul_dumb.run(self)

            log.info("building u3p")

            self.zipfile = zip.ZipFile(os.path.join (self.dist_dir, "%s-%s.u3p" % (self.getTemplateVariable('shortAppName'),self.getTemplateVariable('appVersion'),)), 'w', zip.ZIP_DEFLATED)

            self.addDirectFile ("miro.u3i", "manifest\\manifest.u3i")
            self.addDirectFile ("Miro.ico", "manifest\\Miro.ico")
            self.addDirectFile ("U3Action.exe", "host\\U3Action.exe")

            self.addFile ("%s.exe" % (self.getTemplateVariable('shortAppName'),))
            self.addFile ("%s.ico" % (self.getTemplateVariable('shortAppName'),))
            self.addFile ("%s_MovieData.exe" % (self.getTemplateVariable('shortAppName')))
            self.addFile ("moviedata_util.py")
            self.addFile ("application.ini")
            self.addGlob ("*.dll")

            self.addDirectory ("chrome")
            self.addDirectory ("components")
            self.addDirectory ("defaults")
            self.addDirectory ("resources")
            self.addDirectory ("vlc-plugins")
            self.addDirectory ("plugins")
            self.addDirectory ("xulrunner")
            self.addDirectory ("imagemagick")

            self.zipfile.close()

        def addDirectFile(self, filename, path):
            print "Compressing %s as %s" % (filename, path)
            self.zipfile.write (os.path.join (self.dist_dir, filename), path)

        def addGlob(self, wildcard, src = None, dest = None):
            import glob
            if src is None:
                src = self.dist_dir
            if dest is None:
                dest = "device/"
            length = len(src)
            wildcard = os.path.join (src, wildcard)
            for filename in iglob(wildcard):
                if filename[:length] == (src):
                    filename = filename[length:]
                    while len(filename) > 0 and (filename[0] == '/' or filename[0] == '\\'):
                        filename = filename[1:]
                print "Compressing %s" % (filename,)
                self.zipfile.write (os.path.join (src, filename), os.path.join (dest, filename))

        def addFile(self, filename, src = None, dest = None):
            if src is None:
                src = self.dist_dir
            if dest is None:
                dest = "device/"
            length = len(src)
            if filename[:length] == (src):
                filename = filename[length:]
                while len(filename) > 0 and (filename[0] == '/' or filename[0] == '\\'):
                    filename = filename[1:]
            print "Compressing %s" % (filename,)
            self.zipfile.write (os.path.join (src, filename), os.path.join (dest, filename))

        def addDirectory (self, dirname, src = None, dest = None):
            if src is None:
                src = self.dist_dir
            for root, dirs, files in os.walk (os.path.join (src, dirname)):
                for name in files:
                    self.addFile (os.path.join (root, name), src, dest)

if __name__ == "__main__":
    setup(
        windows=[
            {
                'script': 'Miro.py',
                'icon_resources': [(0, "Miro.ico")],
            },
            {
                'script': 'Miro_Downloader.py',
                'icon_resources': [(0, "Miro.ico")],
            }
            ],
        ext_modules = ext_modules,
        packages = [
            'miro',
            'miro.dl_daemon',
            'miro.dl_daemon.private',
            'miro.frontends',
            'miro.frontends.widgets',
            'miro.frontends.widgets.gtk',
            'miro.plat',
            'miro.plat.renderers',
            'miro.plat.frontends',
            'miro.plat.frontends.widgets',
        ],
        package_dir = {
            'miro': portable_dir,
            'miro.plat': platform_package_dir,
        },
        data_files = data_files,
        cmdclass = {
            'build_py': build_py,
            'build_ext': build_ext,
            'install_data': install_data,
            'build_movie_data_util': build_movie_data_util,
            'bdist_miro': bdist_miro,
            'bdist_nsis': bdist_nsis,
            'runmiro': runmiro,
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
