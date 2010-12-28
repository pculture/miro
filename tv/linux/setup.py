#!/usr/bin/env python

# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

################################################################
## No user-serviceable parts inside                           ##
################################################################

import sys

# verify we have required bits for compiling Miro

try:
    from Pyrex.Compiler import Version
    if Version.version.split(".") < ["0", "9", "6", "4"]:
        print "Pyrex 0.9.6.4 or greater required.  You have version %s." % Version.version
        sys.exit(1)
except ImportError:
    print "Pyrex not found.  Please install Pyrex."
    sys.exit(1)

from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.errors import DistutilsOptionError
from distutils.util import change_root
from distutils import dir_util, log, sysconfig
from glob import glob
from string import Template
import distutils.command.install_data
import os
import pwd
import subprocess
import platform
import re
import time
import shutil

from Pyrex.Distutils import build_ext

#### useful paths to have around ####
def is_root_dir(d):
    """
    bdist_rpm and possibly other commands copies setup.py into a subdir of
    linux.  This makes it hard to find the root directory.  We work
    our way up the path until our is_root_dir test passes.
    """
    return os.path.exists(os.path.join(d, "MIRO_ROOT"))

def get_root_dir():
    root_try = os.path.abspath(os.path.dirname(__file__))
    while True:
        if is_root_dir(root_try):
            root_dir = root_try
            break
        if root_try == '/':
            raise RuntimeError("Couldn't find Miro root directory")
        root_try = os.path.abspath(os.path.join(root_try, '..'))
    return root_dir

root_dir = get_root_dir()
portable_dir = os.path.join(root_dir, 'lib')
portable_frontend_dir = os.path.join(portable_dir, 'frontends')
portable_xpcom_dir = os.path.join(portable_frontend_dir, 'widgets', 'gtk',
                                  'xpcom')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
test_dir = os.path.join(portable_dir, 'test')
resource_dir = os.path.join(root_dir, 'resources')
extensions_dir = os.path.join(root_dir, 'extensions')
platform_dir = os.path.join(root_dir, 'linux')
platform_package_dir = os.path.join(platform_dir, 'plat')
platform_widgets_dir = os.path.join(platform_package_dir, 'frontends',
                                    'widgets')

# insert the root_dir to the beginning of sys.path so that we can
# pick up portable and other packages
sys.path.insert(0, root_dir)

# later when we install the portable modules, they will be in the miro
# package, but at this point, they are in a package named "lib", so
# let's hack it
import lib
sys.modules['miro'] = lib
import plat
sys.modules['miro'].plat = plat

# little hack to get the version from the current app.config.template
from miro import util
app_config = os.path.join(resource_dir, 'app.config.template')
appVersion = util.read_simple_config_file(app_config)['appVersion']

# RPM hack
if 'bdist_rpm' in sys.argv:
    appVersion = appVersion.replace('-', '_')

def getlogin():
    """Does a best-effort attempt to return the login of the user running the
    script.
    """
    try:
        return os.environ['LOGNAME']
    except KeyError:
        pass
    try:
        return os.environ['USER']
    except KeyError:
        pass
    pwd.getpwuid(os.getuid())[0]

def read_file(path):
    f = open(path)
    try:
        return f.read()
    finally:
        f.close()

def write_file(path, contents):
    f = open(path, 'w')
    try:
        f.write(contents)
    finally:
        f.close()

def expand_file_contents(path, **values):
    """Do a string expansion on the contents of a file using the same rules as
    string.Template from the standard library.
    """
    template = Template(read_file(path))
    expanded = template.substitute(**values)
    write_file(path, expanded)

def get_command_output(cmd, warnOnStderr=True, warnOnReturnCode=True):
    """Wait for a command and return its output.  Check for common errors and
    raise an exception if one of these occurs.
    """
    p = subprocess.Popen(cmd, shell=True, close_fds=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if warnOnStderr and stderr != '':
        raise RuntimeError("%s outputted the following error:\n%s" % (cmd, stderr))
    if warnOnReturnCode and p.returncode != 0:
        raise RuntimeError("%s had non-zero return code %d" % (cmd, p.returncode))
    return stdout

def parse_pkg_config(command, components, options_dict = None):
    """Helper function to parse compiler/linker arguments from
    pkg-config and update include_dirs, library_dirs, etc.

    We return a dict with the following keys, which match up with keyword
    arguments to the setup function: include_dirs, library_dirs, libraries,
    extra_compile_args.

    Command is the command to run (pkg-config, etc).
    Components is a string that lists the components to get options for.

    If options_dict is passed in, we add options to it, instead of starting
    from scratch.
    """
    if options_dict is None:
        options_dict = {
            'include_dirs' : [],
            'library_dirs' : [],
            'runtime_dirs' : [],
            'libraries' : [],
            'extra_compile_args' : []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = get_command_output(commandLine).strip()
    for comp in output.split():
        prefix, rest = comp[:2], comp[2:]
        if prefix == '-I':
            options_dict['include_dirs'].append(rest)
        elif prefix == '-L':
            options_dict['library_dirs'].append(rest)
        elif prefix == '-l':
            options_dict['libraries'].append(rest)
        else:
            options_dict['extra_compile_args'].append(comp)

    commandLine = "%s --variable=libdir %s" % (command, components)
    output = get_command_output(commandLine).strip()
    options_dict['runtime_dirs'].append(output)

    return options_dict

def package_exists(package_name):
    """
    Return True if the package is present in the system.  False otherwise.
    The check is made with pkg-config.
    """
    # pkg-config returns 0 if the package is present
    return subprocess.call(['pkg-config', '--exists', package_name]) == 0

def generate_miro():
    f = open(os.path.join(platform_dir, "miro"), "w")
    f.write(
"""#!/bin/sh
# This file is generated by setup.py.
GDBDEBUG=0

for arg in $@
do
    case $arg in
    "--gdb")       GDBDEBUG=1;;
    esac
done

if [ $GDBDEBUG = 1 ]
then
    echo "GDB DEBUGGING MODE."
    PYTHON=`which python`
    GDB=`which gdb`

    if [ -z $GDB ]
    then
        echo "gdb cannot be found on your path.  aborting....";
        exit;
    fi

    $GDB -ex 'set breakpoint pending on' -ex 'run' --args $PYTHON ./miro.real --sync "$@"
else
    miro.real "$@"
fi
""")
    f.close()


#### Xlib Extension ####
ngrams_ext = \
    Extension("miro.ngrams",
        [os.path.join(portable_dir, 'ngrams.c')],
    )

xlib_ext = \
    Extension("miro.plat.xlibhelper",
        [os.path.join(platform_package_dir, 'xlibhelper.pyx')],
        library_dirs = ['/usr/X11R6/lib'],
        libraries = ['X11'],
    )

pygtkhacks_ext = \
    Extension("miro.frontends.widgets.gtk.pygtkhacks",
        [os.path.join(portable_frontend_dir, 'widgets', 'gtk',
                      'pygtkhacks.pyx')],
        **parse_pkg_config('pkg-config',
            'pygobject-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
    )

webkitgtkhacks_ext = \
    Extension("miro.frontends.widgets.gtk.webkitgtkhacks",
        [os.path.join(portable_frontend_dir, 'widgets', 'gtk',
                      'webkitgtkhacks.pyx')],
        **parse_pkg_config('pkg-config',
            'gtk+-2.0 webkit-1.0')
    )

#### Build the data_files list ####
def listfiles(path):
    all_files = [f for f in glob(os.path.join(path, '*')) if os.path.isfile(f)
                 if not f.endswith("~")]
    return all_files

data_files = []
# append the root resource directory.
# filter out app.config.template (which is handled specially)
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
data_files.append(('/usr/share/miro/resources/', files))

# handle the sub directories.
for dir in ('searchengines',
        'images',
        'testdata',
        'conversions',
        'devices',
        os.path.join('testdata', 'conversions'),
        os.path.join('testdata', 'feedparsertests', 'feeds'),
        os.path.join('testdata', 'feedparsertests', 'output'),
        os.path.join('testdata', 'stripperdata'),
        os.path.join('testdata', 'httpserver'),
        os.path.join('testdata', 'locale', 'fr', 'LC_MESSAGES')):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/miro/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))

# add extension files
for root, dirs, files in os.walk(extensions_dir):
    extroot = root[len(extensions_dir)+1:]
    files = [os.path.join(root, f) for f in files
             if (not f.endswith("~") and not "#" in f)]
    data_files.append((
        os.path.join('/usr/share/miro/resources/extensions/', extroot),
        files))

for mem in ["24", "48", "72", "128"]:
    d = os.path.join("icons", "hicolor", "%sx%s" % (mem, mem), "apps")
    source = os.path.join(platform_dir, d, "miro.png")
    dest = os.path.join("/usr/share/", d)
    data_files.append((dest, [source]))

# add the desktop file, mime data, and man page
data_files += [
    ('/usr/share/miro/resources',
     [os.path.join(root_dir, 'CREDITS')]),
    ('/usr/share/pixmaps',
     glob(os.path.join(platform_dir, 'miro.xpm'))),
    ('/usr/share/applications',
     [os.path.join(platform_dir, 'miro.desktop')]),
    ('/usr/share/mime/packages',
     [os.path.join(platform_dir, 'miro.xml')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.1.gz')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.real.1.gz')]),
]


# if we're not doing "python setup.py clean", then we can do a bunch of things
# that have file-related side-effects
if not "clean" in sys.argv:
    generate_miro()
    # gzip the man page
    os.system ("gzip -9 < %s > %s" % (os.path.join(platform_dir, 'miro.1'), os.path.join(platform_dir, 'miro.1.gz')))
    # copy miro.1.gz to miro.real.1.gz so that lintian complains less
    os.system ("cp %s %s" % (os.path.join(platform_dir, 'miro.1.gz'), os.path.join(platform_dir, 'miro.real.1.gz')))


#### Our specialized install_data command ####
class install_data(distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        source = os.path.join(resource_dir, 'app.config.template')
        dest = '/usr/share/miro/resources/app.config'

        config_file = util.read_simple_config_file(source)
        print "Trying to figure out the git revision...."
        if config_file["appVersion"].endswith("git"):
            revision = util.query_revision()
            if revision is None:
                revision = "unknown"
                revisionurl = "unknown"
                revisionnum = "unknown"
            else:
                revisionurl = revision[0]
                revisionnum = revision[1]
                revision = "%s - %s" % (revisionurl, revisionnum)
        else:
            revisionurl = ""
            revisionnum = ""
            revision = ""
        print "Using %s" % revisionnum

        if self.root:
            dest = change_root(self.root, dest)
        self.mkpath(os.path.dirname(dest))
        # We don't use the dist utils copy_file() because it only copies
        # the file if the timestamp is newer
        shutil.copyfile(source, dest)
        expand_file_contents(dest, APP_REVISION=revision,
                             APP_REVISION_NUM=revisionnum,
                             APP_REVISION_URL=revisionurl,
                             APP_PLATFORM='linux',
                             BUILD_MACHINE="%s@%s" % (getlogin(),
                                                      os.uname()[1]),
                             BUILD_TIME=str(time.time()),
                             MOZILLA_LIB_PATH="")
        self.outfiles.append(dest)

        locale_dir = os.path.join (resource_dir, "locale")

        for source in glob (os.path.join (locale_dir, "*.mo")):
            lang = os.path.basename(source)[:-3]
            if 'LINGUAS' in os.environ and lang not in os.environ['LINGUAS']:
                continue
            dest = '/usr/share/locale/%s/LC_MESSAGES/miro.mo' % lang
            if self.root:
                dest = change_root(self.root, dest)
            self.mkpath(os.path.dirname(dest))
            self.copy_file(source, dest)
            self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()


class test_system(Command):
    description = "Allows you to test configurations without compiling or running."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # FIXME - try importing and all that other stuff to make sure
        # we have most of the pieces here?
        pass

#### install_theme installs a specified theme .zip
class install_theme(Command):
    description = 'Install a provided theme to /usr/share/miro/themes'
    user_options = [("theme=", None, 'ZIP file containing the theme')]

    def initialize_options(self):
        self.theme = None

    def finalize_options(self):
        if self.theme is None:
            raise DistutilsOptionError, "must supply a theme ZIP file"
        if not os.path.exists(self.theme):
            raise DistutilsOptionError, "theme file does not exist"
        import zipfile
        if not zipfile.is_zipfile(self.theme):
            raise DistutilsOptionError, "theme file is not a ZIP file"
        zf = zipfile.ZipFile(self.theme)
        appConfig = zf.read('app.config')
        themeName = None
        for line in appConfig.split('\n'):
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.lstrip()
                if name == 'themeName':
                    themeName = value
        if themeName is None:
            raise DistutilsOptionError, "invalid theme file"
        self.zipfile = zf
        self.theme_name = themeName
        self.theme_dir = '/usr/share/miro/themes/%s' % themeName

    def run(self):
        if os.path.exists(self.theme_dir):
            shutil.rmtree(self.theme_dir)
        os.makedirs(self.theme_dir)
        for name in self.zipfile.namelist():
            if name.startswith('xul/'):
                # ignore XUL stuff, we don't need it on Linux
                continue
            print 'installing', os.path.join(self.theme_dir, name)
            if name[-1] == '/':
                os.makedirs(os.path.join(self.theme_dir, name))
            else:
                f = file(os.path.join(self.theme_dir, name), 'wb')
                f.write(self.zipfile.read(name))
                f.close()
        print """%s theme installed.

To use this theme, run:

    miro --theme="%s"
""" % (self.theme_name, self.theme_name)

class clean(Command):
    description = 'Cleans the build and dist directories'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if os.path.exists('./build/'):
            print "removing build directory"
            shutil.rmtree('./build/')

        if os.path.exists('./dist/'):
            print "removing dist directory"
            shutil.rmtree('./dist/')

ext_modules = []
ext_modules.append(ngrams_ext)
ext_modules.append(xlib_ext)
ext_modules.append(pygtkhacks_ext)
ext_modules.append(webkitgtkhacks_ext)

#### Run setup ####
setup(name='miro',
    version=appVersion,
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getmiro.com/',
    download_url='http://www.getmiro.com/downloads/',
    scripts = [
        os.path.join(platform_dir, 'miro'),
        os.path.join(platform_dir, 'miro.real')
    ],
    data_files=data_files,
    ext_modules=ext_modules,
    packages = [
        'miro',
        'miro.dl_daemon',
        'miro.test',
        'miro.dl_daemon.private',
        'miro.frontends',
        'miro.frontends.cli',
        'miro.frontends.profilewidgets',
        'miro.frontends.shell',
        'miro.frontends.widgets',
        'miro.frontends.widgets.gtk',
        'miro.plat',
        'miro.plat.frontends',
        'miro.plat.frontends.widgets',
        'miro.plat.renderers',
    ],
    package_dir = {
        'miro': portable_dir,
        'miro.test': test_dir,
        'miro.plat': platform_package_dir,
    },
    cmdclass = {
        'test_system': test_system,
        'build_ext': build_ext,
        'install_data': install_data,
        'install_theme': install_theme,
        'clean': clean,
    }
)
