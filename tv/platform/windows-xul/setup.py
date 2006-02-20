import os.path
import os
import copy
import sys
import string
import subprocess

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
BINARY_KIT_ROOT = defaultBinaryKitRoot

# Set BOOST_LIB, BOOST_INCLUDE_PATH, and BOOST_RUNTIMES as appropriate
# for the location of Boost, the version you built, and the compiler
# you used. If you are unsure, search you hard drive for a file named
# "boost_python*". If there is more than one, you probably already
# know what you're doing.
# NEEDS: better accomodate non-vc71 compilers in binary kit?
BOOST_ROOT = os.path.join(BINARY_KIT_ROOT, 'boost', 'win32')
BOOST_LIB_PATH = os.path.join(BOOST_ROOT, 'lib')
BOOST_LIB = os.path.join(BOOST_LIB_PATH, 'boost_python-vc71-mt-1_33.lib')
BOOST_INCLUDE_PATH = os.path.join(BOOST_ROOT, 'include', 'boost-1_33')
BOOST_RUNTIMES = [
    os.path.join(BOOST_LIB_PATH, 'boost_python-vc71-mt-1_33.dll'),
    ]

# The 'Democracy.exe' launcher stub, currently provided only in the
# binary kit.
STUB_PATH = os.path.join(BINARY_KIT_ROOT, 'stub', 'Democracy.exe')

# Runtime library DLLs to distribute with the application. Set as
# appropriate for your compiler.
# NEEDS: a future version should autodetect these, by walking DLLs a la
# py2exe.
COMPILER_RUNTIMES = [
    # Visual C++ 7.1 C runtime library (required by Python, if nothing else)
    os.path.join(BINARY_KIT_ROOT, 'vc71redist', 'msvcr71.dll'),
    # Visual C++ 7.1 C++ runtime library (required by Boost-Python)
    os.path.join(BINARY_KIT_ROOT, 'vc71redist', 'msvcp71.dll'),
    ]

# Python runtime DLL to distribute with the application. Usually, the
# Python installer drops it in c:\windows\system32.
PYTHON_RUNTIMES = [
    "C:\\windows\\system32\\python24.dll",
    ]

# Path to the Mozilla "xulrunner" distribution. We include a build in
# the Binary Kit to save you a minute or two, but if you want to be
# more up-to-date, nightlies are available from Mozilla at:
#  http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/
XULRUNNER_DIR = os.path.join(BINARY_KIT_ROOT, "xulrunner")

# Path to "xpidl" and "xpt_link", Mozilla tools to compile IDL
# interface files to type libraries. Get by building Mozilla or
# downloading the Gecko Runtime Engine SDK, or the XUL SDK (XDK) when
# it is released.
IDL_TOOLS_PATH = os.path.join(BINARY_KIT_ROOT, "idltools")

# Path to the IDL include directory, containing declarations of the
# basic Mozilla interfaces. Get this out of the XUL SDK when it's
# released, or the GRE SDK for now.
IDL_INCLUDE_PATH = os.path.join(BINARY_KIT_ROOT, "idlinclude")

# Path to a build of PyXPCOM, the glue that binds Python to
# Mozilla. As of this writing, the only way to get this is to build
# Mozilla, apply a patch or two, and then build PyXPCOM from within
# the tree, and finally fish various files out of the 'dist' directory
# produced and organize them the way this build script expects. This
# setting should point to a directory that has contains:
#  (1) a subdirectory 'components', containing 'pyloader.dll', copied
#      from '$objdir/dist/bin/components' in the Mozilla tree; and
#  (2) a subdirectory 'python', containing a subdirectory 'xpcom',
#      being a copy of the directory tree rooted at
#      '$objdir/dist/bin/python/xpcom' in the Mozilla tree.
# In theory PyXPCOM should be built from the exact same source tree as
# xulrunner, with the same options. In practice you are often okay
# as long you don't mix and match between release and debug builds, so
# you can take the PyXPCOM in the Binary Kit and often succeed in
# running it alongside your choice of xulrunner nightlies.
PYXPCOM_DIR = os.path.join(BINARY_KIT_ROOT, "pyxpcom")

# Path to a build of our patched VLC Mozilla plugin. This directory
# should contain 'npvlc.dll' and 'vlcintf.xpt'.
VLC_MOZ_PLUGIN_DIR = os.path.join(BINARY_KIT_ROOT, "mozplugin")

# Path to a build of vlc plugins to go along with that Mozilla plugin
VLC_PLUGINS_DIR = os.path.join(VLC_MOZ_PLUGIN_DIR, "vlc-plugins")

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.core import setup
from distutils.extension import Extension
from distutils.core import Command
from distutils import log
import os
import sys
import shutil
import re
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'windows-xul'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0] = [
    os.path.join(root, 'platform', platform),
    os.path.join(root, 'platform'),
    os.path.join(root, 'portable'),
]
root = os.path.normpath(root)

#### The fasttypes extension ####

fasttypes_ext = \
    Extension("fasttypes", 
        sources = [os.path.join(root, 'portable', 'fasttypes.cpp')],
        extra_objects = [BOOST_LIB],
        include_dirs = [BOOST_INCLUDE_PATH]
    )

os.environ['PATH'] = r'%s;%s' % (os.environ['PATH'], BOOST_LIB_PATH)

# Private extension modules to build.
ext_modules = [
    fasttypes_ext,

    # Pyrex sources.
    #Extension("vlc", [os.path.join(root, 'platform',platform, 'vlc.pyx')],libraries=["simplevlc"]),
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
]

###############################################################################

# WHEN LAUNCHING DIRECTLY ('test mode'):
#
# 1) Build any extensions; add results to sys.path
# 2) Add all application Python directories to sys.path
# 3) Find 'resources'
# 4) Build a complete xulrunner image in a temporary directory
# 5) Find the application template, including application.ini
# 6) Compile all IDL files in 'idl'. [HACK: save results into the original
#    copy of the application tree..]
# 7) Adjust PATH and PYTHONPATH. Set RUNXUL_RESOURCES to point at 'resources'.
#    to tell child process where to find them.
# 8) Shell out to the xulrunner binary in the built xulrunner image, passing
#    the path to application.ini.
#
# WHEN BUILDING A REDISTRIBUTABLE IMAGE:
#
# 1) Build any extensions; add results to sys.path
# 2) Add all application Python directories to sys.path
# 3) Walk the module dependency graph to get a list of all Python files
#    that should be distributed, including extensions.
# 4) Find 'resources'
# 5) Make the distribution directory. Flush it if it already exists.
# 6) Copy the application template to the distribution directory.
# 7) Build a complete xulrunner image into dist/xulrunner
# 8) Rename dist/xulrunner/xulrunner-stub.exe to dist/dtv.exe
# 9) Compile all IDL files in 'idl'; save result into dist/components
# 10) Copy the Python files identified in step 3 to dist/python
# 11) Identify DLL dependencies and copy them into, as far as I can
#     tell, dist/xulrunner. The roots for the dependency calculation are
#     the pyloader XPCOM module and any Python extension DLLs, filtered
#     to remove any system DLLs. For now, though, we'll just use a
#     static dependency list.
#
# pybridge must be modified to augment sys.path with (XCurProcD)/python
# if present. resource.resourceRoot() has already been modified in what
# should be the appropriate way.

class Common:
    def __init__(self):
        self.templateVars = None

    # NEEDS: if you look at the usage of this function, we're dropping
    # the plugin into the xulrunner plugin directory, rather than the
    # app bundle plugin directory, which is the way you're "supposed"
    # to do it so your app is cleanly separated from xulrunner.
    def copyVLCPluginFiles(self, baseDir, xulrunnerDir):
        destDir = os.path.join(xulrunnerDir, 'plugins')
	if not os.access(destDir, os.F_OK):
	    os.mkdir(destDir)

        pluginFiles = ['npvlc.dll', 'vlcintf.xpt']
        for f in pluginFiles:
            shutil.copy2(os.path.join(VLC_MOZ_PLUGIN_DIR, f), destDir)

        vlcPluginDest = os.path.join(baseDir, "vlc-plugins")
	if not os.access(vlcPluginDest, os.F_OK):
	    os.mkdir(vlcPluginDest)

        vlcPlugins = os.listdir(VLC_PLUGINS_DIR)
        for f in vlcPlugins:
            if f[0] != '.':
                shutil.copy2(os.path.join(VLC_PLUGINS_DIR, f), vlcPluginDest)

    def copyMiscFiles(self, destDir):
        shutil.copy2(os.path.join(root,"license.txt"),destDir)

    def compileIDL(self):
	buildDir = os.path.join(self.bdist_base, "idl")
	pattern = re.compile(r"(.*)\.idl$")
	xpidl = os.path.join(IDL_TOOLS_PATH, "xpidl")
	xpt_link = os.path.join(IDL_TOOLS_PATH, "xpt_link")

	if not os.access(buildDir, os.F_OK):
	    os.mkdir(buildDir)

	idlDir = os.path.join(root, 'platform', platform, 'idl')
	generatedFiles = []
	if not os.access(idlDir, os.F_OK):
	    self.typeLibrary = None
	    return

	for name in os.listdir(idlDir):
	    m = pattern.match(name)
	    if not m:
		continue
	    inPath = os.path.join(idlDir, name)
	    outPath = os.path.join(buildDir, m.group(1) + ".xpt")

	    result = os.spawnl(os.P_WAIT, xpidl, xpidl, "-m", "typelib",
			       "-w", "-v", "-e", outPath,
			       "-I", IDL_INCLUDE_PATH, inPath)
	    if result != 0:
		raise OSError, "Couldn't compile %s (error code %s)" % \
		    (inPath, result)

	    generatedFiles.append(outPath)

	if len(generatedFiles) == 0:
	    self.typeLibrary = None
	    return

	outXpt = os.path.join(self.bdist_base, 'xpcom_typelib.xpt')
        log.info("linking IDL files to %s", outXpt)
	result = os.spawnl(os.P_WAIT, xpt_link, xpt_link, outXpt,
			   *generatedFiles)
	if result != 0:
	    raise OSError, "Couldn't link compiled IDL to %s (error code %s)" \
		% (outXpt, )

	self.typeLibrary = outXpt

    # Fill the app.config.template, to generate the real app.config.
    # NEEDS: Very sloppy. The new file is just dropped in the source tree
    # next to the old one. This also initializes self.templateVars.
    def makeAppConfig(self):
        import util
        revision = util.queryRevision(root)
        if revision is None:
            revision = "unknown"
        else:
            revision = "r%d" % revision

        path = os.path.join(root, 'resources', 'app.config')
        s = open("%s.template" % path, "rt").read()
        s = string.Template(s).safe_substitute(APP_REVISION = revision)
        f = open(path, "wt")
        f.write(s)
        f.close()

        self.templateVars = util.readSimpleConfigFile(path)

    def setTemplateVariable(self, key, value):
        assert self.templateVars, \
            "Must call makeAppConfig before setTemplateVariable"
        self.templateVars[key] = value

    def getTemplateVariable(self, key):
        assert self.templateVars, \
            "Must call makeAppConfig before getTemplateVariable"
        return self.templateVars[key]

    # Given a file <filename>.template, replace all applicable
    # template variables and generate a file <filename> right next to
    # it in the tree. 'Template variables' are anything in app.config,
    # plus anything set with setTemplateVariable.
    # NEEDS: same deal as makeAppConfig: sloppy; shouldn't drop files in
    # the source tree.
    def fillTemplate(self, filename):
        assert self.templateVars, \
            "Must call makeAppConfig before fillTemplate"
        s = open("%s.template" % filename, "rt").read()
        s = string.Template(s).safe_substitute(self.templateVars)
        f = open(filename, "wt")
        f.write(s)
        f.close()

    def fillTemplates(self):
        xulBase = os.path.join(root, 'platform', platform, 'xul')

        self.fillTemplate(os.path.join(xulBase, 'application.ini'))
        self.fillTemplate(os.path.join(xulBase, 'defaults', 'preferences',
                                       'prefs.js'))

        # NEEDS: generalize to do the whole tree, so as to handle all
        # locales
        self.fillTemplate(os.path.join(xulBase, 'chrome', 'locale',
                                       'en-US', 'main.dtd'))        
        self.fillTemplate(os.path.join(xulBase, 'chrome', 'locale',
                                       'en-US', 'about.dtd'))        

###############################################################################

class runxul(Command, Common):
    description = "test run of a Mozilla XUL-based application"

    def __init__(self, *rest):
        Command.__init__(self, *rest)
        Common.__init__(self)

    # List of option tuples: long name, short name (None if no short
    # name), and help string.
    user_options = [
        ('bdist-base=', 'b',
         'base directory for build library (default is build)'),
        ('dist-dir=', 'd',
         "directory to put final built distributions in (default is dist)"),
	('bdist-dir=', 'd',
	 "temporary directory for creating the distribution"),
        ]

    def initialize_options(self):
        self.bdist_base = None
	self.bdist_dir = None
        self.dist_dir = 'dist'

	self.childPythonPaths = []
	self.childDLLPaths = []

    def finalize_options(self):
        if self.bdist_dir is None:
            bdist_base = self.get_finalized_command('bdist').bdist_base
            self.bdist_dir = os.path.join(bdist_base, 'xul')

        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'),
                                   ('bdist_base', 'bdist_base'))

	# Find our 'resources' tree (NEEDS)
	self.appResources = os.path.join(root, 'resources')

    def buildXulrunnerInstallation(self):
	buildBase = os.path.join(self.bdist_base, "xulrunner")
	self.xulrunnerDir = buildBase
	markFile = os.path.join(buildBase, ".xulrunnerBuilt")
	if os.access(markFile, os.F_OK):
	    # Mark file exists. We take this to mean that there is
	    # valid xulrunner tree already built in buildBase.
	    return

        log.info("assembling temporary xulrunner tree in %s" % buildBase)

	# First, copy in the basic Xulrunner distribution.
	copyTreeExceptSvn(XULRUNNER_DIR, buildBase)

	# Then, copy the extra PyXPCOM files over it.
	copyTreeExceptSvn(PYXPCOM_DIR, buildBase)

        # Copy the license file over
        # NEEDS: (huh? this doesn't belong here at all)
        self.copyMiscFiles(self.bdist_base)

        # Finally, drop in our plugins.
        self.copyVLCPluginFiles(self.bdist_base, buildBase)

	# Create the mark file to indicate that we now have a build.
	open(markFile, 'w')

    def run(self):
        self.makeAppConfig()
        self.setTemplateVariable("pyxpcomIsEmbedded", "false")
        self.fillTemplates()                  

        # Build extensions and add results to child search path
        build = self.reinitialize_command('build')
        build.build_base = self.bdist_base
        build.run()
        if build.build_platlib is not None:
	    self.childPythonPaths.append(build.build_platlib)
        if build.build_lib is not None:
	    self.childPythonPaths.append(build.build_lib)

	# Add application Python modules to child search path
	self.childPythonPaths. \
	    extend([
		os.path.join(root, 'platform', platform),
		os.path.join(root, 'platform'),
		os.path.join(root, 'portable'),
		])

	# Put together an xulrunner installation that meets our standards.
	self.buildXulrunnerInstallation()
	xulrunnerBinary = os.path.join(self.xulrunnerDir, "xulrunner")

	# Find application -- presently hardcoded to a tree in
	# 'xul'.
	self.applicationRoot = os.path.join(root, 'platform', platform,
					    'xul')
	applicationIni = os.path.join(self.applicationRoot, 'application.ini')

	# Compile any IDL in the application
        log.info("compiling type libraries")
	self.compileIDL()

	# Run the app. NEEDS: The main hack here is how we write the
	# type library into the source tree, which is pretty odious.
	if self.typeLibrary:
	    # NEEDS: even if we did it this way, ensure that 'components'
	    # exists
	    typeLibraryPath = os.path.join(self.applicationRoot, 'components',
					   'types.xpt')
	    shutil.copy2(self.typeLibrary, typeLibraryPath)

	newEnv = copy.deepcopy(os.environ)
	oldPath = 'PATH' in newEnv and [newEnv['PATH']] or []
	newEnv['PATH'] = \
	    ';'.join(oldPath + self.childDLLPaths)
	oldPyPath = 'PYTHONPATH' in newEnv and [newEnv['PYTHONPATH']] or []
	newEnv['PYTHONPATH'] = \
	    ';'.join(oldPyPath + self.childPythonPaths)
	newEnv['RUNXUL_RESOURCES'] = self.appResources
	print "Starting application"
#	os.execle(xulrunnerBinary, xulrunnerBinary, applicationIni, newEnv)
	os.execle(xulrunnerBinary, xulrunnerBinary, applicationIni, "-jsconsole", "-console", newEnv)

###############################################################################

class bdist_xul_dumb(Command, Common):
    description = "build redistributable directory for Mozilla-based app"

    def __init__(self, *rest):
        Command.__init__(self, *rest)
        Common.__init__(self)

    # List of option tuples: long name, short name (None if no short
    # name), and help string.
    user_options = [
        ('bdist-base=', 'b',
         'base directory for build library (default is build)'),
        ('dist-dir=', 'd',
         "directory to put final built distribution in (default is dist)"),
	('bdist-dir=', 'd',
	 "temporary directory for creating the distribution"),
        ]

    def initialize_options(self):
        # NEEDS: allow 'includes' and 'excludes' options?
        self.bdist_base = None
	self.bdist_dir = None
        self.dist_dir = 'dist'

	self.childPythonPaths = []
	self.childDLLPaths = []

    def finalize_options(self):
        if self.bdist_dir is None:
            bdist_base = self.get_finalized_command('bdist').bdist_base
            self.bdist_dir = os.path.join(bdist_base, 'xul')

        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'),
                                   ('bdist_base', 'bdist_base'))

	# Find our 'resources' tree (NEEDS)
	self.appResources = os.path.join(root, 'resources')
        # Find our various data bits (NEEDS)
	self.xulTemplateDir = os.path.join(root, 'platform', platform,
                                           'xul')

    def run(self):
        self.makeAppConfig()
        self.setTemplateVariable("pyxpcomIsEmbedded", "true")
        self.fillTemplates()                  

        # There are a few modules in the standard library that we want to
        # override with out own copies (well, just one: site.py) -- put them
        # on the path first.
        packagePaths = [os.path.join(root, 'platform', platform, 'overrides')]

        # The standard library (and any installed extensions) come
        # after that.
        packagePaths.extend(sys.path)

        # Build extensions; add them to search path
        build = self.reinitialize_command('build')
        build.build_base = self.bdist_base
        build.run()
        if build.build_platlib is not None:
	    packagePaths.append(build.build_platlib)
        if build.build_lib is not None:
	    packagePaths.append(build.build_lib)

	# Add application Python modules to search path
        # NEEDS: should compile all Python files, and add the *build*
        # directories to the path.
	packagePaths.extend([
                os.path.join(root, 'platform', platform),
		os.path.join(root, 'platform'),
		os.path.join(root, 'portable'),
		])

        # Add PyXPCOM's runtime scripts directory to the search path,
        # and call out a list of top-level modules (those imported by
        # user code or by the C XPConnect code) that are sufficient to
        # cause the dependency scanner to conclude that all of the
        # PyXPCOM scripts are necessary.
        # NEEDS: again, should arrange to have these get built.
	packagePaths.extend([
                os.path.join(PYXPCOM_DIR, "python"),
                ])
        moduleIncludes = [# Public to Python code
                           "xpcom",
                           "xpcom.components",
                           "xpcom.file",
                           "xpcom.register",
                           # Used by C++ XPConnect bridge to Mozilla
                           "xpcom._xpcom",
                           "xpcom.client",
                           "xpcom.server",
                           # This manages to escape but looks important (?)
                           "xpcom.server.enumerator",
                           ]

        # Add other stuff that is necessary to get a functional Python
        # environment.
        moduleIncludes.extend([
                # The Python initialization script.
                "site",
                ])
        packageIncludes = [
            # Make sure all the codecs we need make it in. Otherwise the
            # dependency scanner isn't clever enough to find them.
            "encodings",
            ]

        # Build the list of all Python code and extensions required by
        # the application
        # NEEDS: should bootstrap dependency scan from *.py in component
        # directory..
        log.info("computing module dependencies")
        wellConnectedFile = os.path.join(root, 'portable', 'app.py')
        manifest = self.computePythonManifest(scripts = [wellConnectedFile],
                                              includes = moduleIncludes,
                                              packages = packageIncludes,
                                              path = packagePaths)
        #print '\n'.join(["%s -> %s" % (source, dest) \
        #                 for (source, dest) in manifest])
        
        # Put together the basic skeleton of the application
        log.info("clearing out old build directory if any")
        shutil.rmtree(self.dist_dir, True)
        log.info("copying XUL resources")
        copyTreeExceptSvn(self.xulTemplateDir, self.dist_dir)
        log.info("assembling xulrunner")
        self.xulrunnerOut = os.path.join(self.dist_dir, 'xulrunner')
	copyTreeExceptSvn(XULRUNNER_DIR, self.xulrunnerOut)
        # (Copy *only* the components part, not the Python part; that
        #  got sucked into the dependency scan above)
	copyTreeExceptSvn(os.path.join(PYXPCOM_DIR, 'components'),
                          os.path.join(self.xulrunnerOut, 'components'))

        # Copy the license file over
        self.copyMiscFiles(self.dist_dir)

        self.copyVLCPluginFiles(self.dist_dir, self.xulrunnerOut)

        # Compile and drop in type library
        # NEEDS: make IDL directory configurable
        log.info("compiling type libraries")
        self.compileIDL()
	if self.typeLibrary:
            componentDir = os.path.join(self.dist_dir, 'components')
            if not os.access(componentDir, os.F_OK):
                os.makedirs(componentDir)
            shutil.copy2(self.typeLibrary, componentDir)

        # Copy the files indicated in the manifest to create a complete
        # application package.
        log.info("creating application image")
        imageRoot = os.path.join(self.dist_dir, 'xulrunner', 'python')
        dirsCreated = set()
        for (source, dest) in manifest:
            dest = os.path.join(imageRoot, dest)
            destDir = os.path.dirname(dest)
            if destDir not in dirsCreated:
                if not os.access(destDir, os.F_OK):
                    os.makedirs(destDir)
                dirsCreated.add(destDir)
            shutil.copy2(source, dest)

        # Copy required DLLs.
        # NEEDS: shared library dependency scan, starting with pyloader
        # and any python extensions, instead of this static list
        log.info("copying DLL dependencies")
        # NEEDS: Some Microsoft documentation says that the DLL search
        # order is (1) the directory containing the "executable module
        # for the current process", (2) the current directory, (3)
        # GetSystemDirectory(), (4) GetWindowsDirectory(), and finally
        # (5) PATH. That would suggest that we could put the DLLs in
        # the same directory as xulrunner.exe and everything would be
        # grand. In fact, everything is grand only if the DLLs are on
        # PATH or in the current directory.
        #
        # Elsewhere, I read that the search order changed recently
        # (SP1?): "No longer is the current directory searched first
        # when loading DLLs! ... The default behavior now is to look
        # in all the system locations first, then the current
        # directory, and finally any user-defined paths. This will
        # have an impact on your code if you install a DLL in the
        # application's directory because Windows Server 2003 no
        # longer loads the 'local' DLL if a DLL of the same name is in
        # the system directory." (Google for "Development Impacts of
        # Security Changes in Windows Server 2003.) The purpose of the
        # change was to eliminate an opportunity for an attacker to
        # put trojaned versions of the system DLLs into an application
        # directory. The article is mum on this concept of searching
        # the "executable module for the current directory."
        #
        # For now, let's dump the DLLs in the same directory as
        # xulrunner-stub.exe (aka dtv.exe) and require that the
        # current directory be the directory that contains the binary
        # when it is run. This can easily be accomplished with a
        # Windows shortcut, which is the way end-users will be
        # starting the program. [And in fact the new Democracy.exe
        # launcher now ensures that xulrunner is already run with the
        # current directory set appropriately.]
#        dllDistDir = self.xulrunnerOut
        dllDistDir = self.dist_dir
        allRuntimes = PYTHON_RUNTIMES + BOOST_RUNTIMES + COMPILER_RUNTIMES
        for runtime in allRuntimes:
            shutil.copy2(runtime, dllDistDir)

        # Copy in our application's resources.
        log.info("copying application resources")
        copyTreeExceptSvn(self.appResources,
                          os.path.join(self.dist_dir, 'resources'))
        shutil.copy2("Democracy.nsi", self.dist_dir)
        shutil.copy2("Democracy.ico", self.dist_dir)

        # NEEDS: set permissions/attributes on everything uniformly?

        # Finally, create the top-level executable, and rename
        # xulrunner.exe so the user is not confused and surprised to
        # see it in the process list (and in firewall/antivirus
        # dialogs, etc.)
        log.info("creating executable")
        shutil.copy2(STUB_PATH, self.dist_dir)
        os.rename(os.path.join(self.xulrunnerOut, "xulrunner.exe"),
                  os.path.join(self.xulrunnerOut, "Democracy.exe"))
        os.remove(os.path.join(self.xulrunnerOut, "xulrunner-stub.exe"))

    def computePythonManifest(self, path=None, scripts=[], packages=[],
                              includes=[], excludes=[]):
        """Determine the files that need to be copied to get a complete image
        of the Python modules and extensions used by the application,
        by tracing all of the dependencies of a set of Python scripts and
        packages. The packages will be included in the list of files to
        copy; the scripts will not be.

        @param path: The search path when resolving package references;
        think of it as the simulated runtime value of sys.path.
        @type path: list of string

        @param scripts: Filenames of the scripts to use as dependency roots.
        @type scripts: string iterable
        @param packages: Names of the packages to use as dependency roots,
        such as might be passed to 'import'
        @type packages: string iterable

        @param includes: Names of modules that should be included
        even if they are not found by the dependency scan
        @type includes: string iterable
        @param excludes: Names of modules that should not be included even
        if they are found by the dependency scan (if a module is given both
        as an 'include' and an 'exclude', 'include' takes priority)
        @type includes: string iterable

        @return: (source, dest) tuples giving the absolute source path of a
        file that should be copied, and the relative destination path
        (including filename) to which it should be copied in the image
        @rtype: (string, string) list

        @bug: Packages are not the same as modules. A dependency root
        cannot be given as a package if it does not represent a
        directory, that is, if it does not correspond to a file named
        '__init__.py'. List it in 'includes' in this case.
        """

        # Put our helper packages on the path, and import them
        helperRoot = os.path.join(root, 'platform', platform, 'tools')
        if not helperRoot in sys.path:
            sys.path.append(helperRoot)
        from modulegraph.find_modules import find_modules
        import modulegraph.modulegraph as mg

        # Run the dependency scan
        moduleGraph = find_modules(path = path,
                                   scripts = scripts, packages = packages,
                                   includes = includes, excludes = excludes)
#        moduleGraph.graphreport()

        # Resolve items found to files, and report any errors detected
        manifest = [] # (absolute source path, relative dest path) tuples
        dotPattern = re.compile(r"\.")
        for item in moduleGraph.flatten():
            if type(item) is mg.MissingModule:
                log.warn("apparently missing module %s" % item.identifier)
            elif type(item) in [mg.ExcludedModule, mg.BuiltinModule,
                                mg.Script]:
                pass
            elif item.filename is None:
                log.warn("missing filename for module %s (? -- type %s)"\
                         % (item.identifier, type(item).__name__))
            elif type(item) in [mg.SourceModule, mg.CompiledModule,
                                mg.Extension, mg.Package]:
                components = dotPattern.split(item.identifier)
                if type(item) is mg.Package:
                    components.append('__init__.py')
                else:
                    # Need to put the correct extension back on. Does this
                    # work in all cases?
                    components[-1:] = [os.path.basename(item.filename)]
                relativePath = os.path.join(*components)
                manifest.append((item.filename, relativePath))
            else:
                log.warn("unrecognized dependency type %s (%s, %s)"\
                         % (type(item).__name__, item.identifier, 
                            item.filename))

        return manifest

###############################################################################

###############################################################################

class bdist_xul (bdist_xul_dumb):
    def run(self):
        bdist_xul_dumb.run(self)

        log.info("building installer")

        nsisVars = {}
        for (ourName, nsisName) in [
            ('appVersion', 'CONFIG_VERSION'),
            ('projectURL', 'CONFIG_PROJECT_URL'),
            ('shortAppName', 'CONFIG_SHORT_APP_NAME'),
            ('longAppName', 'CONFIG_LONG_APP_NAME'),
            ('publisher', 'CONFIG_PUBLISHER'),
            ]:
            nsisVars[nsisName] = self.getTemplateVariable(ourName)

        outputFile = "%s-%s.exe" % \
            (self.getTemplateVariable('shortAppName'),
             self.getTemplateVariable('appVersion'),
             )
        nsisVars['CONFIG_OUTPUT_FILE'] = outputFile

        # Hardcoded elsewhere in this file, so why not here too?
        nsisVars['CONFIG_EXECUTABLE'] = "Democracy.exe"
        nsisVars['CONFIG_ICON'] = "Democracy.ico"

        nsisArgs = ["/D%s=%s" % (k, v) for (k, v) in nsisVars.iteritems()]
        nsisArgs.append(os.path.join(self.dist_dir, "Democracy.nsi"))

        if os.access(outputFile, os.F_OK):
            os.remove(outputFile)
        subprocess.call([NSIS_PATH] + nsisArgs)

def copyTreeExceptSvn(src, dest):
    """Copy the contents of the given source directory into the given
    destination directory, creating the destination directory first if
    necessary. Preserve all file attributes. If the source directory
    contains directories, recursively copy them as well. However,
    under no circumstances copy a file or directory named '.svn'."""

    names = os.listdir(src)
    if not os.access(dest, os.F_OK):
	os.mkdir(dest)
    for name in names:
	if name == ".svn":
	    continue
	srcname = os.path.join(src, name)
	destname = os.path.join(dest, name)
	if os.path.isdir(srcname):
	    copyTreeExceptSvn(srcname, destname)
	else:
	    shutil.copy2(srcname, destname)

setup(
    ext_modules = ext_modules,
    cmdclass = {
	'build_ext': build_ext,
	'runxul': runxul,
	'bdist_xul_dumb': bdist_xul_dumb,
	'bdist_xul': bdist_xul,
	}
)
