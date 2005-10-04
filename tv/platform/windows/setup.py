###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# Set ALL THREE of these as appropriate for the location of Boost, the
# version you built, and the compiler you used. If you are unsure,
# search you hard drive for a file named "boost_python*". If there is
# more than one, you probably already know what you're doing.

BOOST_LIB_PATH = "C:\\Boost\\lib"
BOOST_LIB = "%s\\boost_python-vc71-mt-1_33.lib" % BOOST_LIB_PATH
BOOST_INCLUDE_PATH = "C:\\Boost\\include\\boost-1_33"

# You'll need the Gecko Runtime Engine (GRE) and a corresponding GRE
# SDK in order to build this program. Set their paths here. See
# BUILD.windows for more information.

GRE_SDK_PATH = "c:\\cygwin\\home\\Owner\\bin\\gecko-sdk-i586-pc-msvc-1.7.8"
GRE_PATH = "c:\\Program Files\\Common Files\\mozilla.org\\GRE\\1.7.8_2005051112"
#GRE_SDK_PATH = "c:\\moz\\mozilla\\w32-objdir-debug\\dist\\sdk"
#GRE_PATH = "c:\\moz\\mozilla\\w32-objdir-debug\\dist\\gre"

# IMPORTANT: if you use a GRE that was not installed by the
# mozilla.org installer, you will need to set HARDCODE_GRE_PATH to 1
# here and give the full path to the GRE you want to use, quoted as
# following the model. This will bypass the normal runtime GRE
# location logic and always use the GRE at this absolute path (meaning
# that you probably won't be able to ship your build off your machine
# to anyone who doesn't have a GRE in exactly the same place.) You
# need to do this because the mozilla.org installer sets registry keys
# that are used at runtime to find the GRE, and your GRE will lack
# this registration.

HARDCODE_GRE_PATH = 0
#HARDCODE_GRE_PATH_AS = r'\"c:\\moz\\mozilla\\w32-objdir-debug\\dist\\gre\"'

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

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


#### The WebBrowser extension (deprecated) ####

WebBrowser_ext = Extension('WebBrowser',
                           sources = ['WebBrowser.cpp'],
                           libraries = ['gdi32', 'shell32', 'user32',
                                        'advapi32', 'atl'],
                          )

#### The MozillaBrowser extension ####

# Set this to pass compiler flags to generate debugging information
# and use debugging DLLs when building MozillaBrowser. Still doen't
# help, apparently because py2exe packages the app in such a way
# that the Visual Studio debugger can't find the debugging symbols.
MOZILLABROWSER_DEBUGGING = 1

MozillaBrowser_extra_compile_args = [
    '-DXPCOM_GLUE',
    '-DMOZILLA_STRICT_API',
    '-I%s' % os.path.join(GRE_SDK_PATH, 'include'),
    '-I%s' % os.path.join(root, 'platform', platform, 'MozillaBrowser'),
    '-I%s' % os.path.join(root, 'platform', platform, 'MozillaBrowser'),
    # There is at least one interface (nsIBaseWindow) required for embedding
    # which is not frozen. So, we have no choice but to specially copy in the
    # corresponding header. See README in the directory for a list of
    # interfaces and their status.
    # NEEDS: Presently the directory contains static copies from a Mozilla
    # checkout. It might be better to autogenerate the headers from IDL if we
    # can automatically find fresh IDL files.
    '-I%s' % os.path.join(root, 'platform', platform, 'MozillaBrowser',
	                  'unfrozen'),
    # Use multithreaded DLL libraries:
    MOZILLABROWSER_DEBUGGING and '-MD' or -MDd, 
]

if MOZILLABROWSER_DEBUGGING:
    MozillaBrowser_extra_compile_args.append('-Zi')

if HARDCODE_GRE_PATH:
    MozillaBrowser_extra_compile_args. \
	append("-DHARDCODED_GRE_PATH=\"%s\"" % HARDCODE_GRE_PATH_AS)

MozillaBrowser_libraries = [
    # GRE
    'embed_base_s',
    'nspr4',
    'plc4',
    'plds4',
    'xpcomglue',
#    'xpcomglue_s', # Doesn't fly -- it doesn't contain GRE_Init().
    # Windows
    'user32',
    'advapi32',
]

MozillaBrowser_sources = [
    'MozillaBrowser\\MozillaBrowser.cpp',
    'MozillaBrowser\\MozillaBrowser_methods.cpp',
    'MozillaBrowser\\helpers.cpp',
    'MozillaBrowser\\Control.cpp',
    'MozillaBrowser\\Chrome.cpp',
    'MozillaBrowser\\Listener.cpp',
]

MozillaBrowser_ext = \
    Extension('MozillaBrowser',
        sources = MozillaBrowser_sources,
        libraries = MozillaBrowser_libraries,
	library_dirs = ['%s\\lib' % GRE_SDK_PATH],
	extra_compile_args = MozillaBrowser_extra_compile_args,
    )

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
    # Full-blown C++ extension modules.
#   WebBrowser_ext, # deprecated
    MozillaBrowser_ext,
    fasttypes_ext,
    #vlchelper.info.getExtension(root),

    # Pyrex sources.
    Extension("simplevlc", [os.path.join(root, 'platform','windows', 'simplevlc.pyx')],libraries=["simplevlc"]),
    Extension("database", [os.path.join(root, 'portable', 'database.pyx')]),
    Extension("template", [os.path.join(root, 'portable', 'template.pyx')]),
]

# As documented at
# http://www.mozilla.org/projects/xpcom/glue/Component_Reuse.html
# we still have to ship nspr4.dll even though we're using XPCom glue;
# Mozilla needs it to bootstrap dynamic library loading. See also
# http://www.mail-archive.org/mozilla-embedding@mozilla.org/msg04024.html
# So, we need to put an actual, live installation of the GRE on the
# library path at build time for distutils to find and package up.
# You can see what's happening by running dumpbin /imports on
# build/lib.win32-2.4/MozillaBrowser.pyd.
os.environ['PATH'] = r'%s;%s' % (os.environ['PATH'], GRE_PATH)

setup(
    console = ['DTV.py'],
    ext_modules = ext_modules,
    options=dict(
        py2exe=py2exe_options,
    ),
    cmdclass = {'build_ext': build_ext}
)

def copyTreeExceptSvn(src, dest):
    names = os.listdir(src)
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
    print 'Removing old %s if any' % resourceTarget
    shutil.rmtree(resourceTarget, True)
    print 'Populating %s' % resourceTarget
    copyTreeExceptSvn(resourceRoot, resourceTarget)

    # NEEDS: plds4.dll from the GRE is in fact needed at runtime, but
    # somehow it slips past distutils. (It doesn't seem to appear in the
    # import table as shown by dumpbin /imports so this is understandable.)
    # Ideally there would be some flag to tell distutils to include it
    # anyway, but for now we'll just copy it in ourselves.
    shutil.copy(os.path.join(GRE_PATH, "plds4.dll"), distRoot)
