##############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

import distutils.command.build
import distutils.command.build_py
from distutils.core import setup
from distutils.extension import Extension
from distutils.core import Command
from glob import glob
import os
import sys
import shutil
from string import Template
import popen2
from Pyrex.Distutils import build_ext
from distutils import dep_util

# Some useful info to have around
platform = 'gtk-x11'
platform_dir = os.path.abspath(os.path.dirname(__file__))
root = os.path.abspath(os.path.join(platform_dir, '..', '..'))
portable_dir = os.path.join(root, 'portable')
resource_dir= os.path.join(root, 'resources')
bittorrent_dir = os.path.join(portable_dir, 'BitTorrent')
frontend_implementation_dir = os.path.join(platform_dir, 
        'frontend_implementation')
xine_dir = os.path.join(platform_dir, 'xine')
svnversion = os.popen('svnversion %s' % root).read().strip()

#### The fasttypes extension ####

fasttypes_ext = \
    Extension("democracy.fasttypes", 
        sources = [os.path.join(root, 'portable', 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )

#### MozillaBrowser Extension ####
def parsePkgConfig(command, components, options_dict = None):
    """Helper function to parse compiler/linker arguments from 
    pkg-config/mozilla-config and update include_dirs, library_dirs, etc.
    """

    if options_dict is None:
        options_dict = {
            'include_dirs' : [],
            'library_dirs' : [],
            'libraries' : [],
            'extra_compile_args' : []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = os.popen(commandLine, 'r').read().strip()
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

mozilla_browser_options = parsePkgConfig("pkg-config" , 
        "gtk+-2.0 glib-2.0 pygtk-2.0")
parsePkgConfig("mozilla-config", "string dom gtkembedmoz necko xpcom",
        mozilla_browser_options)
# mozilla-config doesn't get gtkembedmoz one for some reason
mozilla_browser_options['libraries'].append('gtkembedmoz') 
mozilla_browser_ext = Extension("democracy.MozillaBrowser",
        [ os.path.join(frontend_implementation_dir,'MozillaBrowser.pyx'),
          os.path.join(frontend_implementation_dir,'MozillaBrowserXPCOM.cc'),
        ],
        runtime_library_dirs=mozilla_browser_options['library_dirs'],
        **mozilla_browser_options)


#### Xine Extension ####
xine_options = parsePkgConfig('pkg-config', 
        'libxine pygtk-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
xine_ext = Extension('democracy.xine', [
        os.path.join(xine_dir, 'xine.pyx'),
        os.path.join(xine_dir, 'xine_impl.c'),
        ], **xine_options)

# Private extension modules to build.
ext_modules = [
    # Full-blown C++ extension modules.
    fasttypes_ext,
    # Pyrex sources.
    mozilla_browser_ext,
    xine_ext,
    Extension("democracy.database", 
            [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("democracy.template", 
            [os.path.join(root, 'portable', 'template.pyx')]),
]


if 0:
    class democracy_build(distutils.command.build):
        """democracy_build extends the distutils build command to make it run
        build_democracy as well as the usually commands."""
        def get_subcommands(self):
            commands = distutils.command.build.get_subcommands(self)
            return commands

class build_py (distutils.command.build_py.build_py):
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

    def get_data_files(self):
        """Generate list of '(package,src_dir,build_dir,filenames)' tuples.

        In addition to the default list, we include the files in the democracy
        resource directory and glade/democracy.glade.
        """

        data_files = distutils.command.build_py.build_py.get_data_files(self)
        resource_dest = os.path.join(self.build_lib, 'democracy', 'resources')
        for path, dirs, files in os.walk(resource_dir):
            # ignore subversion directories
            if '.svn' in dirs:
                dirs.remove('.svn')
            # ignore app.config files (these get built specially)
            if os.path.samefile(path, resource_dir):
                filter_list = ['app.config', 'app.config.template']
                files = [f for f in files if f not in filter_list]
            # add the files
            src_dir = os.path.abspath(path)
            assert path.startswith(resource_dir)
            relative_path = path[len(resource_dir):]
            if relative_path.startswith(os.path.sep):
                relative_path = relative_path[1:]
            build_dir = os.path.join(resource_dest, relative_path)
            data_files.append(('democracy', path, build_dir, files))
        data_files.append(('democracy', 'glade', resource_dest,
            ['democracy.glade']))
        return data_files
    
    def build_app_config(self):
        """Build the app.config file from app.config.template."""

        source = os.path.join(resource_dir, 'app.config.template')
        f = open(source)
        template = Template(f.read())
        f.close()
        built_template = template.substitute(APP_REVISION=svnversion,
                APP_PLATFORM=platform)
        dest = os.path.join(self.build_lib, 'democracy', 'resources',
                'app.config')
        self.mkpath(os.path.dirname(dest))
        f = open(dest, 'wt')
        f.write(built_template)
        f.close()

    def run(self):
        """Do the build work.  In addition to the default implementation, we
        also build the democracy package from the platform and portable code
        and install the resources as package data.  We also automatically
        build app.config.
        """

        for (package, module, module_file) in self.find_democracy_modules():
            assert package == 'democracy'
            self.build_module(module, module_file, package)
        self.build_app_config()
        return distutils.command.build_py.build_py.run(self)

setup(name='democracy', 
    version='0.8,', 
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getdemocracy.com/',
    download_url='http://www.getdemocracy.com/downloads/',
    scripts = ['democracyplayer.py'],
    ext_modules = ext_modules, 
    packages = [
        'democracy.frontend_implementation',
        'democracy.BitTorrent'
    ],
    package_dir = {
        'democracy.frontend_implementation' : 'frontend_implementation',
        'democracy.BitTorrent' : bittorrent_dir,
    },
    cmdclass = {'build_ext': build_ext, 'build_py': build_py}
)
