# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import os
import re
import sys
import time
import string
import py2app
import shutil
import plistlib
import datetime

from glob import glob
from distutils.core import setup
from Pyrex.Distutils import build_ext
from distutils.extension import Extension
from distutils.cmd import Command
from py2app.build_app import py2app

import tarfile

# =============================================================================
# Get command line parameters
# =============================================================================

forceUpdate = False
if '--force-update' in sys.argv:
    sys.argv.remove('--force-update')
    forceUpdate = True

# =============================================================================
# Find the top of the source tree and set search path
# GCC3.3 on OS X 10.3.9 doesn't like ".."'s in the path so we normalize it
# =============================================================================

root = os.path.dirname(os.path.abspath(sys.argv[0]))
root = os.path.join(root, '../..')
root = os.path.normpath(root)

sandbox_root_dir = os.path.normpath(os.path.normpath(os.path.join(root, '..', '..')))
sandbox_dir = os.path.join(sandbox_root_dir, 'sandbox')

portable_dir = os.path.join(root, 'portable')
sys.path[0:0]=[portable_dir]

# =============================================================================
# Make sure that we have a local sandbox setup
# =============================================================================

if not os.path.exists(sandbox_dir):
    print "Sandbox not found, let's set it up..."
    result = os.system("bash setup_sandbox.sh -r %s" % sandbox_root_dir )
    if not result == 0:
        print "Sandbox setup failed..."
        sys.exit(1)
        
# =============================================================================
# Only now may we import things from our own tree
# =============================================================================

import template_compiler

# =============================================================================
# Look for the Boost library in various common places.
# - we assume that both the library and the include files are installed in the
#   same directory sub-hierarchy.
# - we look for library and include directory in:
#   - our local sandbox
#   - the standard '/usr/local' tree
#   - Darwinports' standard '/opt/local' tree
#   - Fink's standard '/sw' tree
# =============================================================================

BOOST_LIB_DIR = None
BOOST_INCLUDE_DIR = None
BOOST_VERSION = None

for rootDir in (sandbox_dir, '/usr/local', '/opt/local', '/sw'):
    libItems = glob(os.path.join(rootDir, 'lib/libboost_python-1_3*.dylib'))
    incItems = glob(os.path.join(rootDir, 'include/boost-1_3*/'))
    if len(libItems) == 1 and len(incItems) == 1:
        BOOST_LIB_DIR = os.path.dirname(libItems[0])
        BOOST_INCLUDE_DIR = incItems[0]
        match = re.search(r'libboost_python-(.*)\.dylib', libItems[0])
        BOOST_VERSION = match.groups()[0]

if BOOST_LIB_DIR is None or BOOST_INCLUDE_DIR is None:
    print 'Boost library could not be found, interrupting build.'
    sys.exit(1)
else:
    print 'Boost library (version %s) found in %s' % (BOOST_VERSION, BOOST_LIB_DIR)

# =============================================================================
# Get subversion revision information.
# =============================================================================

import util
revision = util.queryRevision(root)
if revision is None:
    revisionURL = 'unknown'
    revisionNum = '0000'
    revision = 'unknown'
else:
    revisionURL, revisionNum = revision
    revision = '%s - %s' % revision

# =============================================================================
# Inject the revision number into app.config.template to get app.config.
# =============================================================================

appConfigTemplatePath = os.path.join(root, 'resources/app.config.template')
appConfigPath = os.path.join(root, 'resources/app.config')

def fillTemplate(templatepath, outpath, **vars):
    s = open(templatepath, 'rt').read()
    s = string.Template(s).safe_substitute(**vars)
    f = open(outpath, "wt")
    f.write(s)
    f.close()

fillTemplate(appConfigTemplatePath,
             appConfigPath,
             BUILD_MACHINE="%s@%s" % (os.getlogin(),
                                      os.uname()[1]),
             BUILD_TIME=str(time.time()),
             APP_REVISION = revision, 
             APP_REVISION_URL = revisionURL, 
             APP_REVISION_NUM = revisionNum, 
             APP_PLATFORM = 'osx')

# =============================================================================
# Update the Info property list.
# =============================================================================

def updatePListEntry(plist, key, conf):
    entry = plist[key]
    plist[key] = string.Template(entry).safe_substitute(conf)

conf = util.readSimpleConfigFile(appConfigPath)
infoPlist = plistlib.readPlist(u'Info.plist')

updatePListEntry(infoPlist, u'CFBundleGetInfoString', conf)
updatePListEntry(infoPlist, u'CFBundleIdentifier', conf)
updatePListEntry(infoPlist, u'CFBundleName', conf)
updatePListEntry(infoPlist, u'CFBundleShortVersionString', conf)
updatePListEntry(infoPlist, u'CFBundleVersion', conf)
updatePListEntry(infoPlist, u'NSHumanReadableCopyright', conf)

# =============================================================================
# Now that we have a config, we can process the image name
# =============================================================================

if "--make-dmg" in sys.argv:
    # Change this to change the name of the .dmg file we create
    imgName = "%s-%4d-%02d-%02d.dmg" % (
	conf['shortAppName'],
        datetime.date.today().year,
        datetime.date.today().month,
        datetime.date.today().day)
    sys.argv.remove('--make-dmg')
else:
    imgName = None

# =============================================================================
# Create daemon.py
# =============================================================================

fillTemplate(os.path.join(root, 'portable/dl_daemon/daemon.py.template'),
             os.path.join(root, 'portable/dl_daemon/daemon.py'),
             **conf)

# =============================================================================
# Get a list of additional resource files to include
# =============================================================================

excludedResources = ['.svn', '.DS_Store']
resourceFiles = [os.path.join('Resources', x) for x in os.listdir('Resources') if x not in excludedResources]
resourceFiles.append('qt_extractor.py')

# =============================================================================
# Prepare the frameworks we're going to use
# =============================================================================

def extract_binaries(source, target):
    if forceUpdate and os.path.exists(target):
        shutil.rmtree(target, True)
    
    if os.path.exists(target):
        print "    (all skipped, already there)"
    else:
        os.makedirs(target)
        rootpath = os.path.join(os.path.dirname(root), 'dtv-binary-kit-mac/%s' % source)
        binaries = glob(os.path.join(rootpath, '*.tar.gz'))
        if len(binaries) == 0:
            print "    (all skipped, not found in binary kit)"
        else:
            for binary in binaries:
                tar = tarfile.open(binary, 'r:gz')
                try:
                    for member in tar.getmembers():
                        if os.path.basename(member.name) not in ('._Icon\r', 'Icon\r'):
                            tar.extract(member, target)
                finally:
                    tar.close()

print 'Extracting frameworks to build directory...'
frameworks_path = os.path.join(root, 'platform/osx/build/frameworks')
extract_binaries('frameworks', frameworks_path)
frameworks = glob(os.path.join(frameworks_path, '*.framework'))

# =============================================================================
# Define the clean task
# =============================================================================

class clean(Command):
    user_options = []

    def initialize_options(self):
        return None

    def finalize_options(self):
        return None

    def run(self):
        print "Removing old build directory..."
        try:
            shutil.rmtree('build')
        except:
            pass
        print "Removing old dist directory..."
        try:
            shutil.rmtree('dist')
        except:
            pass
        print "Removing old app..."
        try:
            shutil.rmtree('%s.app'%conf['shortAppName'])
        except:
            pass
        print "Removing old compiled templates..."
        try:
            for filename in os.listdir(os.path.join("..","..","portable","compiled_templates")):
                if not filename.startswith(".svn"):
                    filename = os.path.join("..","..","portable","compiled_templates",filename)
                    if os.path.isdir(filename):
                        shutil.rmtree(filename)
                    else:
                        os.remove(filename)
        except:
            pass

# =============================================================================
# Define our custom build task
# =============================================================================

class mypy2app(py2app):
        
    def run(self):
        global root, imgName, conf
        print "------------------------------------------------"
        
        print "Building %s v%s (%s)" % (conf['longAppName'], conf['appVersion'], conf['appRevision'])

        template_compiler.compileAllTemplates(root)

        py2app.run(self)

        # Setup some variables we'll need

        bundleRoot = os.path.join(self.dist_dir, '%s.app/Contents'%conf['shortAppName'])
        execRoot = os.path.join(bundleRoot, 'MacOS')
        rsrcRoot = os.path.join(bundleRoot, 'Resources')
        fmwkRoot = os.path.join(bundleRoot, 'Frameworks')
        cmpntRoot = os.path.join(bundleRoot, 'Components')
        prsrcRoot = os.path.join(rsrcRoot, 'resources')

        # Py2App seems to have a bug where alias builds would get 
        # incorrect symlinks to frameworks, so create them manually. 

        for fmwk in glob(os.path.join(fmwkRoot, '*.framework')): 
            if os.path.islink(fmwk): 
                dest = os.readlink(fmwk) 
                if not os.path.exists(dest): 
                    print "Fixing incorrect symlink for %s" % os.path.basename(fmwk) 
                    os.remove(fmwk) 
                    os.symlink(os.path.dirname(dest), fmwk)

        # Embed the Quicktime components
        
        print 'Copying Quicktime components to application bundle'
        extract_binaries('qtcomponents', cmpntRoot)

        # Copy our own portable resources

        print "Copying portable resources to application bundle"

        if forceUpdate and os.path.exists(prsrcRoot):
            shutil.rmtree(prsrcRoot, True)

        if os.path.exists(prsrcRoot):
            print "    (all skipped, already bundled)"
        else:
            os.mkdir(prsrcRoot)
            for resource in ('css', 'images', 'searchengines', 'dtvapi.js', 'statictabs.xml'):
                src = os.path.join(root, 'resources', resource)
                rsrcName = os.path.basename(src)
                if os.path.isdir(src):
                    dest = os.path.join(prsrcRoot, rsrcName)
                    copy = shutil.copytree
                else:
                    dest = os.path.join(prsrcRoot, rsrcName)
                    copy = shutil.copy
                copy(src, dest)
                print "    %s" % dest
            os.mkdir(os.path.join(prsrcRoot, 'templates'))
            for js in glob(os.path.join(root, 'resources', 'templates/*.js')):
                dest = os.path.join(prsrcRoot, 'templates', os.path.basename(js))
                copy(js, dest)
                print "    %s" % dest
                

        # Install the final app.config file

        print "Copying config file to application bundle"
        shutil.move(appConfigPath, os.path.join(prsrcRoot, 'app.config'))

        # Copy the gettext MO files in a 'locale' folder inside the
        # application bundle resources folder. Doing this manually at
        # this stage instead of automatically through the py2app
        # options allows to avoid having an intermediate unversioned
        # 'locale' folder.

        print "Copying gettext MO files to application bundle"

        localeDir = os.path.join(root, 'resources/locale')
        lclDir = os.path.join(rsrcRoot, 'locale')
        if forceUpdate and os.path.exists(lclDir):
            shutil.rmtree(lclDir, True);

        if os.path.exists(lclDir):
            print "    (all skipped, already bundled)"
        else:
            for source in glob(os.path.join(localeDir, '*.mo')):
                lang = os.path.basename(source)[:-3]
                dest = os.path.join(lclDir, lang, 'LC_MESSAGES/miro.mo')
                os.makedirs(os.path.dirname(dest))
                shutil.copy2(source, dest)
                print "    %s" % dest
        
        # Wipe out incomplete lproj folders
        
        print "Wiping out incomplete lproj folders"
        
        incompleteLprojs = list()
        for lproj in glob(os.path.join(rsrcRoot, '*.lproj')):
            if os.path.basename(lproj) != 'English.lproj':
                nibs = glob(os.path.join(lproj, '*.nib'))
                if len(nibs) == 0:
                    print "    Removing %s" % os.path.basename(lproj)
                    incompleteLprojs.append(lproj)
                else:
                    print "    Keeping  %s" % os.path.basename(lproj)
                    
        for lproj in incompleteLprojs:
            if os.path.islink(lproj):
                os.remove(lproj)
            else:
                shutil.rmtree(lproj)
        
        # Check that we haven't left some turds in the application bundle.
        
        wipeList = list()
        for root, dirs, files in os.walk(os.path.join(self.dist_dir, '%s.app'%conf['shortAppName'])):
            for excluded in ('.svn', 'unittest'):
                if excluded in dirs:
                    dirs.remove(excluded)
                    wipeList.append(os.path.join(root, excluded))
        
        if len(wipeList) > 0:
            print "Wiping out unwanted data from the application bundle."
            for folder in wipeList:
                print "    %s" % folder
                shutil.rmtree(folder)

        if imgName is not None:
            print "Building image..."

            imgDirName = os.path.join(self.dist_dir, "img")
            imgPath = os.path.join(self.dist_dir, imgName)

            try:
                shutil.rmtree(imgDirName)
            except:
                pass
            try:
                os.remove(imgPath)
            except:
                pass

            os.mkdir(imgDirName)
            os.mkdir(os.path.join(imgDirName,".background"))

            os.rename(os.path.join(self.dist_dir,"%s.app"%conf['shortAppName']),
                      os.path.join(imgDirName, "%s.app"%conf['shortAppName']))
            shutil.copyfile("Resources-DMG/dmg-ds-store",
                            os.path.join(imgDirName,".DS_Store"))
            shutil.copyfile("Resources-DMG/background.tiff",
                            os.path.join(imgDirName,".background",
                                         "background.tiff"))

            os.system("/Developer/Tools/SetFile -a V \"%s\"" %
                      os.path.join(imgDirName,".DS_Store"))
            os.symlink("/Applications", os.path.join(imgDirName, "Applications"))
            
            # Create the DMG from the image folder

            print "Creating DMG file... "

            os.system("hdiutil create -srcfolder \"%s\" -volname %s -format UDZO \"%s\"" %
                      (imgDirName,
		       conf['shortAppName'],
                       os.path.join(self.dist_dir, "%s.tmp.dmg"%conf['shortAppName'])))

            os.system("hdiutil convert -format UDZO -imagekey zlib-level=9 -o \"%s\" \"%s\"" %
                      (imgPath,
                       os.path.join(self.dist_dir, "%s.tmp.dmg"%conf['shortAppName'])))
                      
            os.remove(os.path.join(self.dist_dir,"%s.tmp.dmg"%conf['shortAppName']))

            print "Completed"
            os.system("ls -la \"%s\"" % imgPath)

# =============================================================================
# Define the native extensions
# =============================================================================

# idletime

idletime_src = glob(os.path.join(root, 'platform', 'osx', 'modules', 'idletime.c'))
idletime_link_args = ['-framework', 'CoreFoundation']

idletime_ext = Extension("idletime", sources=idletime_src, 
                                     extra_link_args=idletime_link_args)

# keychain

keychain_src = glob(os.path.join(root, 'platform', 'osx', 'modules', 'keychain.c'))
keychain_link_args = ['-framework', 'Security']

keychain_ext = Extension("keychain", sources=keychain_src, 
                                     extra_link_args=keychain_link_args)

# qtcomp

qtcomp_src = glob(os.path.join(root, 'platform', 'osx', 'modules', 'qtcomp.c'))
qtcomp_link_args = ['-framework', 'CoreFoundation', '-framework', 'Quicktime']

qtcomp_ext = Extension("qtcomp", sources=qtcomp_src,
                                 extra_link_args=qtcomp_link_args)

# database

database_src = glob(os.path.join(root, 'portable', 'database.pyx'))
database_ext = Extension("database", sources=database_src)

# sorts

sorts_src = glob(os.path.join(root, 'portable', 'sorts.pyx'))
sorts_ext = Extension("sorts", sources=sorts_src)

# fasttypes

fasttypes_src = glob(os.path.join(root, 'portable', 'fasttypes.cpp'))
fasttypes_inc_dirs = [BOOST_INCLUDE_DIR]
fasttypes_lib_dirs = [BOOST_LIB_DIR]
fasttypes_libs = ['boost_python-%s' % BOOST_VERSION]

fasttypes_ext = Extension("fasttypes", sources=fasttypes_src, 
                                       include_dirs=fasttypes_inc_dirs, 
                                       library_dirs=fasttypes_lib_dirs, 
                                       libraries=fasttypes_libs)

# libtorrent

def libtorrent_sources_iterator():
    for root,dirs,files in os.walk(os.path.join(portable_dir, 'libtorrent')):
        if '.svn' in dirs:
            dirs.remove('.svn')
        for file in files:
            if file.endswith('.cpp'):
                yield os.path.join(root,file)

libtorrent_src = list(libtorrent_sources_iterator())
libtorrent_src.remove(os.path.join(portable_dir, 'libtorrent/src/file_win.cpp'))
libtorrent_inc_dirs = [BOOST_INCLUDE_DIR,
                       os.path.join(portable_dir, 'libtorrent', 'include'),
                       os.path.join(portable_dir, 'libtorrent', 'include', 'libtorrent')]
libtorrent_lib_dirs = [BOOST_LIB_DIR]
libtorrent_libs = ['boost_python-%s' % BOOST_VERSION, 
                   'boost_filesystem-%s' % BOOST_VERSION, 
                   'boost_date_time-%s' % BOOST_VERSION, 
                   'boost_thread-%s' % BOOST_VERSION, 
                   'z', 
                   'pthread', 
                   'ssl']
libtorrent_compil_args = ["-DHAVE_INCLUDE_LIBTORRENT_ASIO____ASIO_HPP=1", 
                          "-DHAVE_INCLUDE_LIBTORRENT_ASIO_SSL_STREAM_HPP=1", 
                          "-DHAVE_INCLUDE_LIBTORRENT_ASIO_IP_TCP_HPP=1", 
                          "-DHAVE_PTHREAD=1", 
                          "-DTORRENT_USE_OPENSSL=1", 
                          "-DHAVE_SSL=1",
                          "-DNDEBUG"]

libtorrent_ext = Extension("libtorrent", sources=libtorrent_src, 
                                         include_dirs=libtorrent_inc_dirs,
                                         library_dirs=libtorrent_lib_dirs, 
                                         libraries=libtorrent_libs, 
                                         extra_compile_args=libtorrent_compil_args)

# =============================================================================
# Launch the setup process...
# =============================================================================

py2app_options = dict(
    plist = infoPlist,
    iconfile = os.path.join(root, 'platform/osx/%s.icns'%conf['shortAppName']),
    resources = resourceFiles,
    frameworks = frameworks,
    packages = ['dl_daemon']
)

setup(
    app = ['%s.py'%conf['shortAppName']],
    options = dict(py2app = py2app_options),
    ext_modules = [idletime_ext,
                   keychain_ext,
                   qtcomp_ext,
                   database_ext,
                   sorts_ext,
                   fasttypes_ext,
                   libtorrent_ext],
    cmdclass = { 'build_ext':   build_ext, 
                 'clean':       clean, 
                 'py2app':      mypy2app }
)

