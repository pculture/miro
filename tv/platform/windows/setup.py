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

WebBrowser_ext = Extension('WebBrowser',
                           sources = ['WebBrowser.cpp'],
                           libraries = ['gdi32', 'shell32', 'user32',
                                        'advapi32', 'atl'],
                          )

# NEEDS: clean up for checkin
GRE_SDK_PATH = "c:\\cygwin\\home\\Owner\\bin\\gecko-sdk-i586-pc-msvc-1.7.8"
GRE_PATH = "c:\\Program Files\\Common Files\\mozilla.org\\GRE\\1.7.8_2005051112"
#GRE_SDK_PATH = "c:\\moz\\mozilla\\w32-objdir\\dist\\sdk"
#GRE_PATH = "c:\\moz\\mozilla\\w32-objdir\\dist\\gre"
#GRE_SDK_PATH = "c:\\moz\\mozilla\\w32-objdir-debug\\dist\\sdk"
#GRE_PATH = "c:\\moz\\mozilla\\w32-objdir-debug\\dist\\gre"

# Set this to hardcode GRE_PATH into the binary, instead of letting Mozilla
# perform its usual GRE location procedure using the registry.
HARDCODE_GRE_PATH = 0
# NEEDS: automatically compute (watch the quoting!)
#HARDCODE_GRE_PATH_AS = r'\"c:\\moz\\mozilla\\w32-objdir\\dist\\gre\"'
#HARDCODE_GRE_PATH_AS = r'\"c:\\moz\\mozilla\\w32-objdir-debug\\dist\\gre\"'

MOZILLABROWSER_DEBUGGING = 1

# Get GRE SDK at:
# http://ftp.mozilla.org/pub/mozilla.org/mozilla/releases/mozilla1.7.8/gecko-sdk-i586-pc-msvc-1.7.8.zip 
# Get GRE installer at:
# http://ftp.mozilla.org/pub/mozilla.org/mozilla/releases/mozilla1.7.8/windows-xpi/gre-win32-installer.zip

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
    'MozillaBrowser\\helpers.cpp',
    'MozillaBrowser\\Control.cpp',
    'MozillaBrowser\\Chrome.cpp',
]

MozillaBrowser_ext = \
    Extension('MozillaBrowser',
        sources = MozillaBrowser_sources,
        libraries = MozillaBrowser_libraries,
	library_dirs = ['%s\\lib' % GRE_SDK_PATH],
	extra_compile_args = MozillaBrowser_extra_compile_args,
    )

# Private extension modules to build.
ext_modules = [
    #vlchelper.info.getExtension(root),
    WebBrowser_ext,
    MozillaBrowser_ext,
    # Pyrex sources.
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
    print 'Removing old %s if any' % resourceRoot
    shutil.rmtree(resourceTarget, True)
    print 'Populating %s' % resourceTarget
    shutil.copytree(resourceRoot, resourceTarget)

    # NEEDS: plds4.dll from the GRE is in fact needed at runtime, but
    # somehow it slips past distutils. (It doesn't seem to appear in the
    # import table as shown by dumpbin /imports so this is understandable.)
    # Ideally there would be some flag to tell distutils to include it
    # anyway, but for now we'll just copy it in ourselves.
    shutil.copy(os.path.join(GRE_PATH, "plds4.dll"), distRoot)