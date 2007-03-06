import os
import sys
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

# Get command line parameters

forceUpdate = False
if '--force-update' in sys.argv:
    sys.argv.remove('--force-update')
    forceUpdate = True

if "--make-dmg" in sys.argv:
    # Change this to change the name of the .dmg file we create
    imgName = "Democracy-%4d-%02d-%02d.dmg" % (
        datetime.date.today().year,
        datetime.date.today().month,
        datetime.date.today().day)
    sys.argv.remove('--make-dmg')
else:
    imgName = None

# Find the top of the source tree and set search path
# GCC3.3 on OS X 10.3.9 doesn't like ".."'s in the path so we normalize it

root = os.path.dirname(os.path.abspath(sys.argv[0]))
root = os.path.join(root, '../..')
root = os.path.normpath(root)
sys.path[0:0]=[os.path.join(root, 'portable')]

# Only now may we import things from our own tree

import template_compiler

# Look for the Boost library in various common places.
# - we assume that both the library and the include files are installed in the
#   same directory sub-hierarchy.
# - we look for library and include directory in:
#   - the standard '/usr/local' tree
#   - Darwinports' standard '/opt/local' tree
#   - Fink's standard '/sw' tree

boostLib = None
boostIncludeDir = None
boostSearchDirs = ('/usr/local', '/opt/local', '/sw')

for rootDir in boostSearchDirs:
    libItems = glob(os.path.join(rootDir, 'lib/libboost_python-1_3*.a'))
    incItems = glob(os.path.join(rootDir, 'include/boost-1_3*/'))
    if len(libItems) == 1 and len(incItems) == 1:
        boostLib = libItems[0]
        boostIncludeDir = incItems[0]

if boostLib is None or boostIncludeDir is None:
    print 'Boost library could not be found, interrupting build.'
    sys.exit(1)
else:
    print 'Boost library found (%s)' % boostLib

# Get subversion revision information.

import util
revision = util.queryRevision(root)
if revision is None:
    revisionURL = 'unknown'
    revisionNum = '0000'
    revision = 'unknown'
else:
    revisionURL, revisionNum = revision
    revision = '%s - %s' % revision

# Inject the revision number into app.config.template to get app.config.

appConfigTemplatePath = os.path.join(root, 'resources/app.config.template')
appConfigPath = '/tmp/democracy.app.config'
s = open(appConfigTemplatePath, "rt").read()
s = string.Template(s).safe_substitute(APP_REVISION = revision, 
                                       APP_REVISION_URL = revisionURL, 
                                       APP_REVISION_NUM = revisionNum, 
                                       APP_PLATFORM = 'osx')
f = open(appConfigPath, 'wt')
f.write(s)
f.close()

# Update the Info property list.

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

# Get a list of additional resource files to include

excludedResources = ['.svn', '.DS_Store']
resourceFiles = [os.path.join('Resources', x) for x in os.listdir('Resources') if x not in excludedResources]

# And launch the setup process...

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
            shutil.rmtree('Democracy.app')
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

class mypy2app(py2app):
        
    def embed_binaries(self, source, target):
        print "Copying %s to application bundle" % source

        if forceUpdate and os.path.exists(target):
            shutil.rmtree(target, True)
        
        if os.path.exists(target):
            print "    (all skipped, already bundled)"
        else:
            os.makedirs(target)
            rootpath = os.path.join(os.path.dirname(root), 'dtv-binary-kit-mac/%s' % source)
            binaries = glob(os.path.join(rootpath, '*.tar.gz'))
            if len(binaries) == 0:
                print "    (all skipped, not found in binary kit)"
            else:
                for binary in binaries:
                    tar = tarfile.open(binary, 'r:gz')
                    for member in tar.getmembers():
                        print "    %s" % os.path.join(target, member.name)
                        tar.extract(member, target)
                    tar.close

    def run(self):
        global root, imgName, conf
        print "------------------------------------------------"
        
        print "Building Democracy Player v%s (%s)" % (conf['appVersion'], conf['appRevision'])

        template_compiler.compileAllTemplates(root)

        py2app.run(self)

        # Setup some variables we'll need

        bundleRoot = os.path.join(self.dist_dir, 'Democracy.app/Contents')
        execRoot = os.path.join(bundleRoot, 'MacOS')
        rsrcRoot = os.path.join(bundleRoot, 'Resources')
        fmwkRoot = os.path.join(bundleRoot, 'Frameworks')
        cmpntRoot = os.path.join(bundleRoot, 'Components')
        prsrcRoot = os.path.join(rsrcRoot, 'resources')

        # Create a hard link to the main executable with a different
        # name for the downloader. This is to avoid having 'Democracy'
        # shown twice in the Activity Monitor since the downloader is
        # basically Democracy itself, relaunched with a specific
        # command line parameter.

        print "Creating Downloader hard link."

        srcPath = os.path.join(execRoot, 'Democracy')
        linkPath = os.path.join(execRoot, 'Downloader')

        if os.path.exists(linkPath):
            os.remove(linkPath)
        os.link(srcPath, linkPath)

        # Install frameworks and components
        
        self.embed_binaries('frameworks', fmwkRoot)
        self.embed_binaries('qtcomponents', cmpntRoot)

        # Copy our own portable resources

        print "Copying portable resources to application bundle"

        if forceUpdate and os.path.exists(prsrcRoot):
            shutil.rmtree(prsrcRoot, True)

        if os.path.exists(prsrcRoot):
            print "    (all skipped, already bundled)"
        else:
            os.mkdir(prsrcRoot)
            excludedRsrc = ['app.config.template', 'locale', 'testdata']
            for resource in glob(os.path.join(root, 'resources/*')):
                rsrcName = os.path.basename(resource)
                if rsrcName not in excludedRsrc:
                    if os.path.isdir(resource):
                        dest = os.path.join(prsrcRoot, rsrcName)
                        copy = shutil.copytree
                    else:
                        dest = os.path.join(prsrcRoot, rsrcName)
                        copy = shutil.copy
                    copy(resource, dest)
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

        localeDir = os.path.join (root, 'resources/locale')
        lclDir = os.path.join(rsrcRoot, 'locale')
        if forceUpdate and os.path.exists(lclDir):
            shutil.rmtree(lclDir, True);

        if os.path.exists(lclDir):
            print "    (all skipped, already bundled)"
        else:
            for source in glob(os.path.join(localeDir, '*.mo')):
                lang = os.path.basename(source)[:-3]
                dest = os.path.join(lclDir, lang, 'LC_MESSAGES/democracyplayer.mo')
                os.makedirs(os.path.dirname(dest))
                shutil.copy2(source, dest)
                print "    %s" % dest
        
        # Check that we haven't left some turds in the application bundle.
        
        wipeList = list()
        for root, dirs, files in os.walk(os.path.join(self.dist_dir, 'Democracy.app')):
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

            os.rename(os.path.join(self.dist_dir,"Democracy.app"),
                      os.path.join(imgDirName, "Democracy.app"))
            shutil.copyfile("Resources-DMG/DS_Store",
                            os.path.join(imgDirName,".DS_Store"))
            shutil.copyfile("Resources-DMG/background.tiff",
                            os.path.join(imgDirName,".background",
                                         "background.tiff"))

            os.system("/Developer/Tools/SetFile -a V \"%s\"" %
                      os.path.join(imgDirName,".DS_Store"))
            
            # Create the DMG from the image folder

            print "Creating DMG file... "

            os.system("hdiutil create -srcfolder \"%s\" -volname Democracy -format UDZO \"%s\"" %
                      (imgDirName,
                       os.path.join(self.dist_dir, "Democracy.tmp.dmg")))

            os.system("hdiutil convert -format UDZO -imagekey zlib-level=9 -o \"%s\" \"%s\"" %
                      (imgPath,
                       os.path.join(self.dist_dir, "Democracy.tmp.dmg")))
                      
            os.remove(os.path.join(self.dist_dir,"Democracy.tmp.dmg"))

            print "Completed"
            os.system("ls -la \"%s\"" % imgPath)

py2app_options = dict(
    plist = infoPlist,
    iconfile = os.path.join(root, 'platform/osx/Democracy.icns'),
    resources = resourceFiles,
#    frameworks = frameworks,
    packages = ['dl_daemon']
)

setup(
    app = ['Democracy.py'],
    options = dict(py2app = py2app_options),
    ext_modules = [
        Extension("idletime",  [os.path.join(root, 'platform/osx/modules/idletime.c')], extra_link_args=['-framework', 'CoreFoundation']),
        Extension("keychain",  [os.path.join(root, 'platform/osx/modules/keychain.c')], extra_link_args=['-framework', 'Security']),
        Extension("qtcomp",    [os.path.join(root, 'platform/osx/modules/qtcomp.c')], extra_link_args=['-framework', 'CoreFoundation', '-framework', 'Quicktime']),
        Extension("database",  [os.path.join(root, 'portable/database.pyx')]),
        Extension("sorts",     [os.path.join(root, 'portable/sorts.pyx')]),
        Extension("fasttypes", [os.path.join(root, 'portable/fasttypes.cpp')],
                  extra_objects=[boostLib],
                  include_dirs=[boostIncludeDir])
        ],
    cmdclass = {'build_ext': build_ext,
	        'clean': clean,
                'py2app': mypy2app}
)

