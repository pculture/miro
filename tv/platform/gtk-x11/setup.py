#!/usr/bin/env python2.4

# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

##############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils import dir_util
from distutils import log
from distutils.util import change_root
from glob import glob
from string import Template
import distutils.command.build_py
import distutils.command.build_py
import distutils.command.install_data
import os
import subprocess
import sys
import re

from Pyrex.Distutils import build_ext

#### usefull paths to have around ####
# bdist_rpm and possibly other commands copies setup.py into a subdir of
# platform/gtk-x11.  This makes it hard to find the root directory.  We work
# our way up the path until our is_root_dir test passes.
def is_root_dir(dir):
    return os.path.exists(os.path.join(dir, "DEMOCRACY_ROOT"))

root_try = os.path.abspath(os.path.dirname(__file__))
while True:
    if is_root_dir(root_try):
        root_dir = root_try
        break
    if root_try == '/':
        raise RuntimeError("Couldn't find Democracy root directory")
    root_try = os.path.abspath(os.path.join(root_try, '..'))
portable_dir = os.path.join(root_dir, 'portable')
bittorrent_dir = os.path.join(portable_dir, 'BitTornado')
bittorrent_dir2 = os.path.join(portable_dir, 'BitTornado','BT1')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
test_dir = os.path.join(portable_dir, 'test')
compiled_templates_dir = os.path.join(portable_dir, 'compiled_templates')
compiled_templates_unittest_dir = os.path.join(compiled_templates_dir,'unittest')
resource_dir = os.path.join(root_dir, 'resources')
platform_dir = os.path.join(root_dir, 'platform', 'gtk-x11')
xine_dir = os.path.join(platform_dir, 'xine')
frontend_implementation_dir = os.path.join(platform_dir,
        'frontend_implementation')
debian_package_dir = os.path.join(platform_dir, 'debian_package')

sys.path[0:0] = ['%s/platform/%s' % (root_dir, 'gtk-x11'), '%s/platform' % root_dir, '%s/portable' % root_dir]

import template_compiler
template_compiler.compileAllTemplates(root_dir)

# little hack get the version from the current app.config.template
import util
app_config = os.path.join(resource_dir, 'app.config.template')
appVersion = util.readSimpleConfigFile(app_config)['appVersion']

# RPM hack
if 'bdist_rpm' in sys.argv:
    appVersion = appVersion.replace('-', '_')

#### utility functions ####
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

def getCommandOutput(cmd, warnOnStderr = True, warnOnReturnCode = True):
    """Wait for a command and return its output.  Check for common errors and
    raise an exception if one of these occurs.
    """

    p = subprocess.Popen(cmd, shell=True, close_fds = True,
            stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    if warnOnStderr and stderr != '':
        raise RuntimeError("%s outputted the following error:\n%s" % 
                (cmd, stderr))
    if warnOnReturnCode and p.returncode != 0:
        raise RuntimeError("%s had non-zero return code %d" % 
                (cmd, p.returncode))
    return stdout

def parsePkgConfig(command, components, options_dict = None):
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
            'libraries' : [],
            'extra_compile_args' : []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = getCommandOutput(commandLine).strip()
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
    return options_dict

#### The fasttypes extension ####
fasttypes_ext = \
    Extension("democracy.fasttypes", 
        sources = [os.path.join(portable_dir, 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )

#### MozillaBrowser Extension ####
packages = getCommandOutput("pkg-config --list-all")
if re.search("^xulrunner-xpcom", packages, re.MULTILINE):
    xpcom = 'xulrunner-xpcom'
    gtkmozembed = 'xulrunner-gtkmozembed'
elif re.search("^mozilla-xpcom", packages, re.MULTILINE):
    xpcom = 'mozilla-xpcom'
    gtkmozembed = 'mozilla-gtkmozembed'
else:
    raise RuntimeError("Can't find xulrunner-xpcom or mozilla-xpcom")
mozilla_browser_options = parsePkgConfig("pkg-config" , 
        "gtk+-2.0 glib-2.0 pygtk-2.0 %s %s" % (gtkmozembed, xpcom))
mozilla_lib_path = parsePkgConfig('pkg-config', 
        '%s' % gtkmozembed)['library_dirs']
# hack to get #include <nsIDOMElementCSSInlineStyle.h> to work.
# For mozilla 1.7, this file is in the dom/ subdirectory, but for xulrunner ,
# it's in the top level.
for dir in mozilla_browser_options['include_dirs']:
    if os.path.exists(os.path.join(dir, 'dom',
        'nsIDOMElementCSSInlineStyle.h')):
        mozilla_browser_options['include_dirs'].append(os.path.join(dir, 'dom'))

mozilla_browser_ext = Extension("democracy.MozillaBrowser",
        [ os.path.join(frontend_implementation_dir,'MozillaBrowser.pyx'),
          os.path.join(frontend_implementation_dir,'MozillaBrowserXPCOM.cc'),
        ],
        runtime_library_dirs=mozilla_lib_path,
        **mozilla_browser_options)
#### Xlib Extension ####
xlib_ext = \
    Extension("democracy.xlibhelper", 
        [ os.path.join(frontend_implementation_dir,'xlibhelper.pyx') ],
        library_dirs = ['/usr/X11R6/lib'],
        libraries = ['X11'],
    )

#### Xine Extension ####
xine_options = parsePkgConfig('pkg-config', 
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
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
files.append(os.path.join(platform_dir, 'glade', 'democracy.glade'))
files.append(os.path.join(platform_dir, 'ui', 'Democracy.xml'))
data_files.append(('/usr/share/democracy/resources/', files))
# handle the sub directories.
for dir in ('templates', 'css', 'images', 'testdata', os.path.join('templates','unittest')):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/democracy/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))
# add the desktop file, icons, mime data, and man page.
data_files += [
    ('/usr/share/pixmaps', 
     glob(os.path.join(platform_dir, 'democracyplayer-*.png'))),
    ('/usr/share/applications', 
     [os.path.join(platform_dir, 'democracyplayer.desktop')]),
    ('/usr/share/mime/packages', 
     [os.path.join(platform_dir, 'democracy.xml')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'democracyplayer.1.gz')]),
]

os.system ("gzip -9 < " + os.path.join(platform_dir, 'democracyplayer.1') + " > " + os.path.join(platform_dir, 'democracyplayer.1.gz'))

#### Our specialized install_data command ####
class install_data (distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        source = os.path.join(resource_dir, 'app.config.template')
        dest = '/usr/share/democracy/resources/app.config'
        revision = util.queryRevision(root_dir)
        if revision is None:
            revision = "unknown"
            revisionurl = "unknown"
            revisionnum = "unknown"
        else:
            revisionurl = revision[0]
            revisionnum = revision[1]
            revision = "%s - %s" % revision
        if self.root:
            dest = change_root(self.root, dest)
        self.mkpath(os.path.dirname(dest))
        self.copy_file(source, dest)
        expand_file_contents(dest, APP_REVISION=revision,
                             APP_REVISION_NUM=revisionnum,
                             APP_REVISION_URL=revisionurl,
                             APP_PLATFORM='gtk-x11')
        self.outfiles.append(dest)

        for lang in ("fr","it","ka","pl","ro"):
            posource = os.path.join (resource_dir, "locale", "%s.po" % lang)
            source = os.path.join (resource_dir, "locale", "%s.mo" % lang)
            os.system ("msgfmt %s -o %s" % (posource, source))
            dest = '/usr/share/locale/%s/LC_MESSAGES/democracyplayer.mo' % lang
            if self.root:
                dest = change_root(self.root, dest)
            self.mkpath(os.path.dirname(dest))
            self.copy_file(source, dest)
            self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()

#### Our specialized build_py command ####
class build_py (distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the democracy
    package.
    """

    def find_democracy_modules(self):
        """Returns a list of modules to go in the democracy directory.  Each
        item has the form (package, module, path).  The trick here is merging
        the contents of the platform/gtk-x11 and portable directories.
        """
        files = glob(os.path.join(portable_dir, '*.py'))
        files.extend(glob(os.path.join(platform_dir, '*.py')))
        rv = []
        for f in files:
            if os.path.samefile(f, __file__):
                continue
            module = os.path.splitext(os.path.basename(f))[0]
            rv.append(('democracy', module, f))
        return rv

    def find_all_modules (self):
        """Extend build_py's module list to include the democracy modules."""
        modules = distutils.command.build_py.build_py.find_all_modules(self)
        modules.extend(self.find_democracy_modules())
        return modules

    def run(self):
        """Do the build work.  In addition to the default implementation, we
        also build the democracy package from the platform and portable code
        and install the resources as package data.  
        """

        for (package, module, module_file) in self.find_democracy_modules():
            assert package == 'democracy'
            self.build_module(module, module_file, package)
        return distutils.command.build_py.build_py.run(self)

#### bdist_deb builds the democracy debian package ####
class bdist_deb (Command):

    description = "Create a deb package"
    user_options = [ ]

    def initialize_options (self):
        pass

    def finalize_options (self):
        bdist_base = self.get_finalized_command('bdist').bdist_base
        self.bdist_dir = os.path.join(bdist_base, 'deb')
        self.dist_dir = self.get_finalized_command('bdist').dist_dir

    def run (self):
        # build all python modules/extensions
        self.run_command('build')
        # copy the built files
        install = self.reinitialize_command('install', reinit_subcommands=1)
        install.root = self.bdist_dir
        install.skip_build = 1
        install.warn_dir = 0
        install.compile = 0
        install.optimize = 0
        log.info("installing to %s" % self.bdist_dir)
        self.run_command('install')
        # strip all extension modules
        extensions = []
        for path, dir, files in os.walk(self.bdist_dir):
            for f in files:
                if f.endswith('.so'):
                    extensions.append(os.path.join(path, f))
        for path in extensions:
            log.info('stripping %s' % path)
            os.system('strip %s' % path)
        # calculate the dependancies for extension modules
        cmd = 'dpkg-shlibdeps -O %s' % ' '.join(extensions)
        extension_deps = getCommandOutput(cmd, warnOnStderr=False).strip()
        extension_deps = extension_deps.replace('shlibs:Depends=', '')
        # copy over the debian package files
        debian_source = os.path.join(debian_package_dir, 'DEBIAN')
        debian_dest = os.path.join(self.bdist_dir, 'DEBIAN')
        self.copy_tree(debian_source, debian_dest)
        # Fill in the version number in the control file
        expand_file_contents(os.path.join(debian_dest, 'control'),
                VERSION=self.distribution.get_version(),
                EXTENSION_DEPS=extension_deps)
        # copy the copyright file
        copyright_source = os.path.join(debian_package_dir, 'copyright')
        copyright_dest = os.path.join(self.bdist_dir, 'usr', 'share', 'doc', 
                    'python2.4-democracy-player')
        self.mkpath(copyright_dest)
        self.copy_file(copyright_source, copyright_dest)
        # ensure the dist directory is around
        self.mkpath(self.dist_dir)
        # create the debian package
        package_basename = "democracy_%s_i386.deb" % \
                self.distribution.get_version()
        package_path  = os.path.join(self.dist_dir, package_basename)
        dpkg_command = "fakeroot dpkg --build %s %s" % (self.bdist_dir, 
                package_path)
        log.info("running %s" % dpkg_command)
        os.system(dpkg_command)
        dir_util.remove_tree(self.bdist_dir)
#### Run setup ####
setup(name='democracy', 
    version=appVersion,
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getdemocracy.com/',
    download_url='http://www.getdemocracy.com/downloads/',
    scripts=[os.path.join(platform_dir, 'democracyplayer')],
    data_files=data_files,
    ext_modules = [
        fasttypes_ext, mozilla_browser_ext, xine_ext, xlib_ext,
        Extension("democracy.database", 
                [os.path.join(portable_dir, 'database.pyx')]),
#        Extension("democracy.feedparser", 
#                [os.path.join(portable_dir, 'feedparser.pyx')]),
        #Extension("democracy.template", 
        #        [os.path.join(portable_dir, 'template.pyx')]),
    ],
    packages = [
        'democracy.frontend_implementation',
        'democracy.BitTornado',
        'democracy.BitTornado.BT1',
        'democracy.dl_daemon',
        'democracy.test',
        'democracy.compiled_templates',
        'democracy.compiled_templates.unittest',
        'democracy.dl_daemon.private',
    ],
    package_dir = {
        'democracy.frontend_implementation' : frontend_implementation_dir,
        'democracy.BitTornado' : bittorrent_dir,
        'democracy.BitTornado.BT1' : bittorrent_dir2,
        'democracy.dl_daemon' : dl_daemon_dir,
        'democracy.test' : test_dir,
        'democracy.compiled_templates' : compiled_templates_dir,
        'democracy.compiled_templates.unittest' : compiled_templates_unittest_dir,
    },
    cmdclass = {
        'build_ext': build_ext, 
        'build_py': build_py,
        'bdist_deb': bdist_deb,
        'install_data': install_data,
    }
)
