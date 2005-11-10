import os.path
import os
import copy
import sys

###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# Set ALL THREE of these as appropriate for the location of Boost, the
# version you built, and the compiler you used. If you are unsure,
# search you hard drive for a file named "boost_python*". If there is
# more than one, you probably already know what you're doing.
# NEEDS: move into Binary Kit
BOOST_LIB_PATH = "C:\\Boost\\lib"
BOOST_LIB = "%s\\boost_python-vc71-mt-1_33.lib" % BOOST_LIB_PATH
BOOST_INCLUDE_PATH = "C:\\Boost\\include\\boost-1_33"

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
    Extension("vlc", [os.path.join(root, 'platform',platform, 'vlc.pyx')],libraries=["simplevlc"]),
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
]

# Method (for now we only connsider launching the app directly from setup.py):
#
# XXX --- THIS IS OBSOLETE, BUT OLD DOCS ARE BETTER THAN NO DOCS --- XXX
#
# 1) Build all of our extensions.
# 2) Copy (or symlink) the xul tree to staging.
# 3) Find all of the idl files in 'idl'. Compile them. Link them and drop
#    the result in staging/components/app.xpt.
# 4) Modify the Python path to be the application's Python path and the
#    extensions -- not for us, but for the child process.
# 5) Copy xulrunner into dist/xulrunner. Copy the pyxpcom files over it.
#    (Or, better, make a symlink farm of the top directory, drop in 'python',
#    and then interpolate the python loader into the application component
#    directory as a symlink.)
# 6) Copy (or symlink) platform-independent resources to dist/resources.
#    Arguably not the best plan.
# 7) Adjust path to include Boost. Make sure it includes an appropriate Python
#    too.
# 8) Ideally, force a component index rebuild. (How? Something about .autoreg?)
# 8) Run xulrunner application.ini
#
# What we should be doing:
# - Trace out Python include dependencies and build one big Python tree that
#   includes not only our modules (those that are actually used) but also
#   those necessary from the standard/site libraries.
# - Trace out DLL dependencies, including Python itself, and dump them all in
#   'lib'. Don't apply this to xulrunner, though -- always include all of
#   it, in its customary location.
# - For efficiency (?), roll XUL resources (content and localization) up into
#   jar files.
# - In the future, we will have an 'official' xpi installer of some sort
#   that we may wish to integrate with.
#   - Maybe 'runxul' for testing, bdist_xpi for a bare xpi,
#     bdist_xulinst for a standalone XUL app installer including xulrunner

class runxul(Command):
    description = "test run of a Mozilla XUL-based application"

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

    def run(self):
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

	# Find our 'resources' tree
	self.appResources = os.path.join(root, 'resources')

	# Put together an xulrunner installation that meets our standards.
	self.buildXulrunnerInstallation()
	xulrunnerBinary = os.path.join(self.xulrunnerDir, "xulrunner")

	# Find application -- presently hardcoded to a tree in
	# 'xul'.
	self.applicationRoot = os.path.join(root, 'platform', platform,
					    'xul')
	applicationIni = os.path.join(self.applicationRoot, 'application.ini')

	# Compile any IDL in the application
	self.compileIDL()

	# Find, ah, other dependencies or something (NEEDS: complete hack,
	# and not even necessary in the runxul case because we already have
	# the libs on the path from building extensions)
	self.childDLLPaths. \
	    extend([
		BOOST_LIB_PATH,
		])

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
	os.execle(xulrunnerBinary, xulrunnerBinary, applicationIni, newEnv)
#	os.execle(xulrunnerBinary, xulrunnerBinary, applicationIni, "-console", newEnv)

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

	# Create the mark file to indicate that we now have a build.
	open(markFile, 'w')

    def compileIDL(self):
	buildDir = os.path.join(self.bdist_base, "idl")
	pattern = re.compile(r"(.*)\.idl$")
	xpidl = os.path.join(IDL_TOOLS_PATH, "xpidl")
	xpt_link = os.path.join(IDL_TOOLS_PATH, "xpt_link")

	if not os.access(buildDir, os.F_OK):
	    os.mkdir(buildDir)

	idlDir = os.path.join(root, 'platform', platform, 'idl')
	generatedFiles = []
        log.info("compiling IDL files to %s" % buildDir)
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

def copyTreeExceptSvn(src, dest):
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
	}
)
