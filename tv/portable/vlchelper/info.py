from distutils.core import setup, Extension
import commands
import re
import os.path
import sys

# Set to the relative path from the root of our application's source
# tree to the directory containing info.py (the root of the VLC
# extension sources)
THIS_DIRECTORY_FROM_ROOT = 'portable/vlchelper'

# Return the absolute path of the root of the VLC tree. 'root' is the
# path to the root of our application's tree.
def getVLCRoot(root):
    try:
	f = open('%s/vlc_root' % root, 'r')
    except IOError:
	print >> sys.stderr, """
*** You cannot build DTV until VLC has been set up. To set up VLC:
***
*** 1) Make sure you have the Subversion version control system installed.
*** 2) Get VLC 0.8.1 using Subversion like this:
***      svn co svn://svn.videolan.org/vlc/branches/0.8.1 vlc
***    where the final 'vlc' is the name of the directory you want to create
***    containing the VLC source tree. (You need the 0.8.1 out of
***    Subversion, not the 0.8.1 source tarball, because the latter is
***    missing the extras/contrib directory that is necessary to build
***    VLC's dependencies.)
*** 3) Build or install VLC's dependencies as necessary. See the instructions
***    appropriate for your platform at:
***      http://developers.videolan.org/vlc/
***    Follow them up to but not including the point where you run 'bootstrap'
***    or 'configure' in the main VLC directory.
*** 4) Run setup-vlc.py <path to top-level VLC directory> in the appropriate
***    DTV platform directory to configure VLC. This runs VLC's bootstrap and 
***    configure scripts with reasonable arguments and creates a file
***    'vlc_root' in the top-level DTV directory so we remember where VLC is.
*** 5) In the top-level VLC directory, run 'make'.
***
*** Then you can run either:
***  * test.sh, to do a quick build of the DTV bundle and run it (the
***    DTV.app bundle that is created contains symlinks to the actual
***    python files if you do this), or
***  * build.sh, to build a distribution-ready copy of DTV.app.
"""
	raise IOError, "%s/vlc_root not found -- VLC is not set up" % root
    path = f.read().rstrip()
    f.close()
    return path

# Return a list of the modules that should be included in the
# bundle. 'root' is the path to the root of our application's tree.
# Example of format: "modules/misc/dummy"
def getModuleList(root):
    string = commands.getoutput("%s/vlc-config --target plugin" % getVLCRoot(root))
    return [i for i in re.compile(' +').split(string) if not re.compile('^ *$').match(i)]

# Create and return a distutils Extension object describing our VLC
# binding module. 'root' is the path to the root of our application's
# tree.
def getExtension(root):
    vlc_root = getVLCRoot(root)
    
    # Calculate compilation arguments
    cFlags = commands.getoutput("%s/vlc-config --cflags vlc" % vlc_root)
    cFlags = re.compile(' +').split(cFlags)
    cFlags[0:0] = [
	'-DSYS_DARWIN', 
	'-I%s' % vlc_root,
	'-I%s/include' % vlc_root,
	'-I%s/extras/contrib/include' % vlc_root,
	]

    # Calculate link arguments
    def fixPath(x):
	# Hack to translate relative paths returned by vlc-config in
	# link arguments to absolute paths, since distutils doesn't
	# invoke the linker from the root VLC directory. Completely
	# heuristic; update as necessary.
	if re.compile("modules/").match(x):
	    return "%s/%s" % (vlc_root, x)
	return x

    linkLine = commands.getoutput("%s/vlc-config --libs vlc builtin" % vlc_root)
    linkLine = re.compile(' +').split(linkLine)
    linkLine = [fixPath(x) for x in linkLine]
    linkLine[0:0] = [
	"%s/lib/libvlc.a" % vlc_root, 
	"-L%s/extras/contrib/vlc-lib" % vlc_root,
	"-L%s/extras/contrib/lib" % vlc_root,
	# Needed to avoid link errors about "local relocation entries
	# in non-writable sections". The problem is that VLC builds
	# libvlc.a assuming it is going to get statically linked into
	# an application, without the -dynamic flag. But then
	# distutils tries to link it into a dynamically loadable
	# extension module. In the future, might look into patching
	# the VLC build system to allow building the entire tree
	# (including dependencies eg ffmpeg) with -dynamic.
	"-Wl,-read_only_relocs,suppress",
	]

    # Figure out which language's linker to use
    linkage = commands.getoutput("%s/vlc-config --linkage vlc builtin" % vlc_root)

    # Figure out how to reference our source files. 'normpath' reduces
    # the likelihood that the resulting path will contain '..' and '.'
    # components, which break distutils (it can't create temporary
    # build directories with such names.)
    sourcePath = os.path.normpath("%s/%s" % (root, THIS_DIRECTORY_FROM_ROOT))

#    sourceFiles = ['vlcmodule.c']
    sourceFiles = [
	'pyvlc/vlcmodule.c', 
	'pyvlc/mediacontrol-init.c', 
	'pyvlc/mediacontrol-core.c',
	]
    return Extension('vlc',
		     sources = ['%s/%s' % (sourcePath, file) 
				for file in sourceFiles],
		     language = linkage,
		     extra_compile_args = cFlags,
		     extra_link_args = linkLine,
		     )
