#!/usr/bin/env python

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

###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# The xine hack helps some systems.
# FIXME - document
USE_XINE_HACK = True


# The following properties allow you to explicitly set xulrunner paths and
# library names in the case that Miro guesses them wrong for your system.
# When setting these, you must make sure that:
#
# 1. The gtkmozembed Python module is compiled against the same xulrunner
#    that you're compiling AND running Miro against.
#
# 2. That you compile and run Miro with xulrunner 1.8 OR 1.9--you can't
#    use both.


# Location of the libxpcom.so file that's used for runtime.
# This is used to set the LD_LIBRARY_PATH environment variable.
#
# It's possible that this path is already in your LD_LIBRARY_PATH in
# which case you don't have to set it at all.
#
# Leave this set to None and Miro will attempt to guess at where it
# is.  This sometimes works.  If it doesn't on your system, let us know
# and we'll try to fix the guessing code.
#
# NOTE: Make sure this comes from the same xulrunner/firefox runtime that
# Miro is compiled against.  If it's wrong, you'll likely see complaints
# of missing symbols when you try to run Miro.
#
# Examples:
# XPCOM_RUNTIME_PATH = "/usr/lib/firefox"
# XPCOM_RUNTIME_PATH = "/usr/lib/xulrunner-1.9.0.1"
XPCOM_RUNTIME_PATH = None

# Location of xulrunner/firefox components for gtkmozembed.set_comp_path.
# See documentation for set_comp_path here:
# http://www.mozilla.org/unix/gtk-embedding.html
#
# Leave this set to None and Miro will attempt to guess at where it
# is.  This sometimes works.  If it doesn't on your system, let us know
# and we'll try to fix the guessing code.
#
# Examples:
# MOZILLA_LIB_PATH = "/usr/lib/xulrunner-1.9.0.1"
MOZILLA_LIB_PATH = None

# The name of the library for the xpcom and gtkmozembed you want to compile
# against on this system.  These strings are passed to pkg-config to get all
# the information Miro needs to compile our browser widget.
#
# You should be able to do the following with the libraries you provide:
#
#    pkg-config --cflags --libs --define-variable=includetype=unstable \
#        <xpcom-library> <gtkmozembed-library>
#
# and get back lots of exciting data.
#
# Set the XULRUNNER_19 flag to True if compiling against xulrunner 1.9 or
# False if compiling against xulrunner 1.8 or some earlier version.
#
# Leave these three set to None and Miro will attempt to guess at values.
# This sometimes works.  If it doesn't on your system, let us know and we'll
# try to fix the guessing code.
#
# NOTE: If you set one of these, you should set all of them.
#
# Examples:
# XPCOM_LIB = "libxul"
# GTKMOZEMBED_LIB = "libxul"
# XULRUNNER_19 = True
#
# XPCOM_LIB = "firefox-xpcom"
# GTKMOZEMBED_LIB = "firefox-gtkmozembed"
# XULRUNNER_19 = False
XPCOM_LIB = None
GTKMOZEMBED_LIB = None
XULRUNNER_19 = None

# The name of the boost library.  Used for building extensions.
BOOST_LIB = 'boost_python'


###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.errors import DistutilsOptionError
from distutils.util import change_root
from distutils import dir_util, log, sysconfig
from glob import glob
from string import Template
import distutils.command.build_py
import distutils.command.install_data
import os
import pwd
import subprocess
import platform
import sys
import re
import time
import shutil

from Pyrex.Distutils import build_ext

#### usefull paths to have around ####
def is_root_dir(d):
    """
    bdist_rpm and possibly other commands copies setup.py into a subdir of
    platform/gtk-x11.  This makes it hard to find the root directory.  We work
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

def is_x64():
    return platform.machine() == "x86_64" or platform.machine() == "amd64"

root_dir = get_root_dir()
portable_dir = os.path.join(root_dir, 'portable')
portable_frontend_dir = os.path.join(portable_dir, 'frontends')
portable_xpcom_dir = os.path.join(portable_frontend_dir, 'widgets', 'gtk',
        'xpcom')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
test_dir = os.path.join(portable_dir, 'test')
resource_dir = os.path.join(root_dir, 'resources')
platform_dir = os.path.join(root_dir, 'platform', 'gtk-x11')
platform_package_dir = os.path.join(platform_dir, 'plat')
platform_widgets_dir = os.path.join(platform_package_dir, 'frontends',
        'widgets')
xine_dir = os.path.join(platform_dir, 'xine')

# insert the root_dir to the beginning of sys.path so that we can
# pick up portable and other packages
sys.path.insert(0, root_dir)

# later when we install the portable modules, they will be in the miro package,
# but at this point, they are in a package named "portable", so let's hack it
import portable
sys.modules['miro'] = portable
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
    pkg-config/mozilla-config and update include_dirs, library_dirs, etc.

    We return a dict with the following keys, which match up with keyword
    arguments to the setup function: include_dirs, library_dirs, libraries,
    extra_compile_args.

    Command is the command to run (pkg-config, mozilla-config, etc).
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

def compile_xine_extractor():
    rv = os.system("gcc %s -o %s `pkg-config --libs --cflags gdk-pixbuf-2.0 glib-2.0 libxine`" % 
                   (os.path.join(platform_dir, "xine/xine_extractor.c"), os.path.join(platform_dir, "xine/xine_extractor")))
    if rv != 0:
        raise RuntimeError("xine_extractor compilation failed.  Possibly missing libxine, gdk-pixbuf-2.0, or glib-2.0.")

def generate_miro(xpcom_path):
    # build a miro script that wraps the miro.real script with an LD_LIBRARY_PATH
    # environment variable to pick up the xpcom we decided to use.
    runtimelib = ""

    f = open(os.path.join(platform_dir, "miro"), "w")
    if xpcom_path:
        runtimelib = "LD_LIBRARY_PATH=%s " % xpcom_path

    f.write( \
"""#!/bin/sh
# This file is generated by setup.py.
DEBUG=0

for arg in $@
do
    case $arg in
    "--debug")    DEBUG=1;;
    esac
done

if [ $DEBUG = 1 ]
then
    echo "DEBUGGING MODE."
    PYTHON=`which python`
    GDB=`which gdb`

    if [ -z $GDB ]
    then
        echo "gdb cannot be found on your path.  aborting....";
        exit;
    fi

    %(runtimelib)s$GDB -ex 'set breakpoint pending on' -ex 'break gdk_x_error' -ex 'run' --args $PYTHON ./miro.real --sync "$@"
else
    %(runtimelib)smiro.real "$@"
fi
""" % { "runtimelib": runtimelib})
    f.close()


#### The fasttypes extension ####
fasttypes_ext = \
    Extension("miro.fasttypes",
        sources = [os.path.join(portable_dir, 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )


##### The libtorrent extension ####
def fetch_sources(portable_dir):
    sources = []
    for root, dirs, files in os.walk(os.path.join(portable_dir, 'libtorrent')):
        if '.svn' in dirs:
            dirs.remove('.svn')
        for file in files:
            if file.endswith('.cpp') or file.endswith('.c'):
                sources.append(os.path.join(root, file))
    return sources

def get_libtorrent_extension(portable_dir):
    libtorrent_installed = False
    try:
        ret = parse_pkg_config("pkg-config", "libtorrent-rasterbar")
        import libtorrent
        libtorrent_installed = True
    except RuntimeError:
        print "libtorrent-rasterbar not installed on this system."
    except ImportError:
        print "python bindings for libtorrent-rasterbar not installed on this system"

    if libtorrent_installed:
        print "libtorrent-rasterbar and python bindings are installed--using system version."
        return None

    include_dirs = [os.path.join(portable_dir, x) for x in
                            ['libtorrent/include', 'libtorrent/include/libtorrent']]

    extra_compile_args = ["-Wno-missing-braces",
                          "-D_FILE_OFFSET_BITS=64",
                          "-DHAVE___INCLUDE_LIBTORRENT_ASIO_HPP=1",
                          "-DHAVE___INCLUDE_LIBTORRENT_ASIO_SSL_STREAM_HPP=1",
                          "-DHAVE___INCLUDE_LIBTORRENT_ASIO_IP_TCP_HPP=1",
                          "-DHAVE_PTHREAD=1", "-DTORRENT_USE_OPENSSL=1", "-DHAVE_SSL=1",
                          "-DNDEBUG=1", "-O2"]

    if is_x64():
        extra_compile_args.append("-DAMD64")

    # check for mt
    libraries = ['z', 'pthread', 'ssl']
    all_libs = []
    if os.path.exists(os.path.join(sysconfig.PREFIX, "lib")):
        all_libs.extend(os.listdir(os.path.join(sysconfig.PREFIX, "lib")))
    if os.path.exists(os.path.join(sysconfig.PREFIX, "lib64")):
        all_libs.extend(os.listdir(os.path.join(sysconfig.PREFIX, "lib64")))
    all_libs = [mem for mem in all_libs if mem.startswith("libboost")]

    def mt_or_not(s, all_libs=all_libs, libraries=libraries):
        for mem in all_libs:
            if mem.startswith("lib%s-mt" % s):
                print "using %s-mt" % s
                libraries += ["%s-mt" % s]
                break
        else:
            print "using %s" % s
            libraries += [s]

    mt_or_not("boost_python")
    mt_or_not("boost_filesystem")
    mt_or_not("boost_date_time")
    mt_or_not("boost_thread")
    # mt_or_not("boost_regex")
    # mt_or_not("boost_serialization")

    config_vars = sysconfig.get_config_vars()
    if "CFLAGS" in config_vars and "-Wstrict-prototypes" in config_vars["CFLAGS"]:
        config_vars["CFLAGS"] = config_vars["CFLAGS"].replace("-Wstrict-prototypes", " ")

    if "OPT" in config_vars and "-Wstrict-prototypes" in config_vars["OPT"]:
        config_vars["OPT"] = config_vars["OPT"].replace("-Wstrict-prototypes", " ")

    sources = fetch_sources(portable_dir)

    # versions of libtorrent prior to 0.14 have this file which we don't want to
    # compile or use
    if os.path.exists(os.path.join(portable_dir, "libtorrent", "src", "file_win.cpp")):
        sources.remove(os.path.join(portable_dir, "libtorrent", "src", "file_win.cpp"))

    return Extension("miro.libtorrent",
                     include_dirs=include_dirs,
                     libraries=libraries,
                     extra_compile_args=extra_compile_args,
                     sources=sources)

libtorrent_ext = get_libtorrent_extension(portable_dir)


#### MozillaBrowser Extension ####
def get_mozilla_stuff():
    try:
        packages = get_command_output("pkg-config --list-all")
    except RuntimeError, error:
        sys.exit("Package config error:\n%s" % (error,))

    if XPCOM_LIB and GTKMOZEMBED_LIB and XULRUNNER_19 != None:
        print "\nUsing XPCOM_LIB, GTKMOZEMBED_LIB and XULRUNNER_19 values...."
        xulrunner19 = XULRUNNER_19
        xpcom_lib = XPCOM_LIB
        gtkmozembed_lib = GTKMOZEMBED_LIB

    else:
        print "\nTrying to figure out xpcom_lib, gtkmozembed_lib, and xulrunner_19 values...."
        xulrunner19 = False
        if re.search("^libxul", packages, re.MULTILINE):
            xulrunner19 = True
            xpcom_lib = 'libxul'
            gtkmozembed_lib = 'libxul'

        elif re.search("^xulrunner-xpcom", packages, re.MULTILINE):
            xpcom_lib = 'xulrunner-xpcom'
            gtkmozembed_lib = 'xulrunner-gtkmozembed'

        elif re.search("^mozilla-xpcom", packages, re.MULTILINE):
            xpcom_lib = 'mozilla-xpcom'
            gtkmozembed_lib = 'mozilla-gtkmozembed'

        elif re.search("^firefox-xpcom", packages, re.MULTILINE):
            xpcom_lib = 'firefox-xpcom'
            gtkmozembed_lib = 'firefox-gtkmozembed'

        else:
            sys.exit("Can't find libxul, xulrunner-xpcom, mozilla-xpcom or firefox-xpcom")

    print "using xpcom_lib: ", repr(xpcom_lib)
    print "using gtkmozembed_lib: ", repr(gtkmozembed_lib)
    print "using xulrunner19: ", repr(xulrunner19)

    # use the XPCOM_RUNTIME_PATH that's set if there's one that's set
    if XPCOM_RUNTIME_PATH:
        print "\nUsing XPCOM_RUNTIME_PATH value...."
        xpcom_runtime_path = XPCOM_RUNTIME_PATH
    else:
        print "\nTrying to figure out xpcom_runtime_path value...."
        xpcom_runtime_path = get_command_output("pkg-config --variable=libdir %s" % xpcom_lib).strip()
    print "using xpcom_runtime_path: ", repr(xpcom_runtime_path)

    mozilla_browser_options = parse_pkg_config("pkg-config",
            "gtk+-2.0 glib-2.0 pygtk-2.0 --define-variable=includetype=unstable %s %s" % (gtkmozembed_lib, xpcom_lib))

    if MOZILLA_LIB_PATH:
        print "\nUsing MOZILLA_LIB_PATH value...."
        mozilla_lib_path = MOZILLA_LIB_PATH
    else:
        print "\nTrying to figure out mozilla_lib_path value...."
        mozilla_lib_path = parse_pkg_config('pkg-config', '%s' % gtkmozembed_lib)['library_dirs']
        mozilla_lib_path = mozilla_lib_path[0]
    print "using mozilla_lib_path: ", repr(mozilla_lib_path)

    mozilla_runtime_path = parse_pkg_config('pkg-config', gtkmozembed_lib)['runtime_dirs']

    # Find the base mozilla directory, and add the subdirs we need.
    def allInDir(directory, subdirs):
        for subdir in subdirs:
            if not os.path.exists(os.path.join(directory, subdir)):
                return False
        return True

    xpcom_includes = parse_pkg_config("pkg-config", xpcom_lib)

    # xulrunner 1.9 has a different directory structure where all the headers
    # are in the same directory and that's already in include_dirs.  so we don't
    # need to do this.
    if not xulrunner19:
        mozIncludeBase = None
        for dir in xpcom_includes['include_dirs']:
            if allInDir(dir, ['dom', 'gfx', 'widget']):
                # we can be pretty confident that dir is the mozilla/firefox/xulrunner
                # base include directory
                mozIncludeBase = dir
                break

        if mozIncludeBase is not None:
            for subdir in ['dom', 'gfx', 'widget', 'commandhandler', 'uriloader',
                           'webbrwsr', 'necko', 'windowwatcher', 'unstable',
                           'embed_base']:
                path = os.path.join(mozIncludeBase, subdir)
                mozilla_browser_options['include_dirs'].append(path)

    nsI = True
    for dir in mozilla_browser_options['include_dirs']:
        if os.path.exists(os.path.join(dir, "nsIServiceManagerUtils.h")):
            nsI = True
            break
        if os.path.exists(os.path.join(dir, "nsServiceManagerUtils.h")):
            nsI = False
            break

    if nsI:
        mozilla_browser_options['extra_compile_args'].append('-DNS_I_SERVICE_MANAGER_UTILS=1')

    # define PCF_USING_XULRUNNER19 if we're on xulrunner 1.9
    if xulrunner19:
        mozilla_browser_options['extra_compile_args'].append('-DPCF_USING_XULRUNNER19=1')

    return mozilla_browser_options, mozilla_lib_path, xpcom_runtime_path, mozilla_runtime_path

mozilla_browser_options, mozilla_lib_path, xpcom_runtime_path, mozilla_runtime_path = get_mozilla_stuff()


#### Xlib Extension ####
xlib_ext = \
    Extension("miro.plat.xlibhelper",
        [ os.path.join(platform_package_dir,'xlibhelper.pyx') ],
        library_dirs = ['/usr/X11R6/lib'],
        libraries = ['X11'],
    )

pygtkhacks_ext = \
    Extension("miro.frontends.widgets.gtk.pygtkhacks",
        [ os.path.join(portable_frontend_dir, 'widgets', 'gtk',
            'pygtkhacks.pyx') ],
        **parse_pkg_config('pkg-config',
            'pygobject-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
    )

mozprompt_ext = \
    Extension("miro.plat.frontends.widgets.mozprompt",
        [
            os.path.join(platform_widgets_dir, 'mozprompt.pyx'),
            os.path.join(platform_widgets_dir, 'PromptService.cc'),
        ],
        **mozilla_browser_options
    )

http_observer_options = mozilla_browser_options.copy()
http_observer_options['include_dirs'].append(portable_xpcom_dir)

httpobserver_ext = \
    Extension("miro.plat.frontends.widgets.httpobserver",
        [
            os.path.join(platform_widgets_dir, 'httpobserver.pyx'),
            os.path.join(portable_xpcom_dir, 'HttpObserver.cc'),
        ],
        **http_observer_options
    )


windowcreator_ext = \
    Extension("miro.plat.frontends.widgets.windowcreator",
        [
            os.path.join(platform_widgets_dir, 'windowcreator.pyx'),
            os.path.join(platform_widgets_dir, 'MiroWindowCreator.cc'),
        ],
        language="c++",
        **mozilla_browser_options
    )


#### Xine Extension ####
xine_options = parse_pkg_config('pkg-config',
        'libxine pygtk-2.0 gtk+-2.0 glib-2.0 gthread-2.0')

# If you get XINE crashes, uncommenting this might fix it. It's
# necessary on Debian Etch and Ubuntu Feisty right now.
#
# We have a horrible workaround for buggy X drivers in xine_impl.c
# controled by this variable
if USE_XINE_HACK:
    print "Using the Xine driver hack. If you experience trouble playing video,\n   try setting USE_XINE_HACK to False in setup.py."
    if xine_options.has_key('define_macros'):
        xine_options['define_macros'].append(('INCLUDE_XINE_DRIVER_HACK', '1'))
    else:
        xine_options['define_macros'] = [('INCLUDE_XINE_DRIVER_HACK', '1')]

xine_ext = Extension('miro.xine', [
                         os.path.join(xine_dir, 'xine.pyx'),
                         os.path.join(xine_dir, 'xine_impl.c'),],
                     **xine_options)


#### Build the data_files list ####
def listfiles(path):
    return [f for f in glob(os.path.join(path, '*')) if os.path.isfile(f)]

data_files = []
# append the root resource directory.
# filter out app.config.template (which is handled specially)
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
data_files.append(('/usr/share/miro/resources/', files))
# handle the sub directories.
for dir in ('searchengines', 'images', 'testdata',
        os.path.join('testdata', 'stripperdata'),
        os.path.join('testdata', 'locale', 'fr', 'LC_MESSAGES')):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/miro/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))


# add the desktop file, icons, mime data, and man page.
data_files += [
    ('/usr/share/pixmaps',
     glob(os.path.join(platform_dir, 'miro-*.png'))),
    ('/usr/share/applications',
     [os.path.join(platform_dir, 'miro.desktop')]),
    ('/usr/share/mime/packages',
     [os.path.join(platform_dir, 'miro.xml')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.1.gz')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.real.1.gz')]),
    ('/usr/lib/miro/',
     [os.path.join(platform_dir, 'xine/xine_extractor')]),
]


# if we're not doing "python setup.py clean", then we can do a bunch of things
# that have file-related side-effects
if not "clean" in sys.argv:
    compile_xine_extractor()
    generate_miro(xpcom_runtime_path)
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
        print "Trying to figure out the svn revision...."
        if config_file["appVersion"].endswith("svn"):
            revision = util.query_revision(root_dir)
            if revision is None:
                revision = "unknown"
                revisionurl = "unknown"
                revisionnum = "unknown"
            else:
                revisionurl = revision[0]
                revisionnum = revision[1]
                revision = "%s - %s" % revision
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
                             APP_PLATFORM='gtk-x11',
                             BUILD_MACHINE="%s@%s" % (getlogin(),
                                                      os.uname()[1]),
                             BUILD_TIME=str(time.time()),
                             MOZILLA_LIB_PATH=mozilla_runtime_path[0])
        self.outfiles.append(dest)

        locale_dir = os.path.join (resource_dir, "locale")

        for source in glob (os.path.join (locale_dir, "*.mo")):
            lang = os.path.basename(source)[:-3]
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

#### Our specialized build_py command ####
class build_py(distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the miro
    package.
    """

    def expand_templates(self):
        conf = util.read_simple_config_file(app_config)
        for path in [os.path.join(portable_dir, 'dl_daemon', 'daemon.py')]:
            template = Template(read_file(path + ".template"))
            expanded = template.substitute(**conf)
            write_file(path, expanded)

    def run (self):
        """Extend build_py's module list to include the miro modules."""
        self.expand_templates()
        return distutils.command.build_py.build_py.run(self)


#### install_theme installs a specifified theme .zip
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
                # ignore XUL stuff, we don't need it on linux
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
ext_modules.append(fasttypes_ext)
ext_modules.append(xine_ext)
ext_modules.append(xlib_ext)
if libtorrent_ext:
    ext_modules.append(libtorrent_ext)
ext_modules.append(pygtkhacks_ext)
ext_modules.append(mozprompt_ext)
ext_modules.append(httpobserver_ext)
ext_modules.append(windowcreator_ext)
ext_modules.append(Extension("miro.database", [os.path.join(portable_dir, 'database.pyx')]))
ext_modules.append(Extension("miro.sorts", [os.path.join(portable_dir, 'sorts.pyx')]))

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
        'build_py': build_py,
        'install_data': install_data,
        'install_theme': install_theme,
        'clean': clean,
    }
)
