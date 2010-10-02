# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import os
import re
import sys
import time
import string
import shutil
import zipfile
import tarfile
import plistlib
import datetime
import subprocess

from glob import glob
# from distutils.util import get_platform
from distutils.file_util import copy_file
from distutils.dir_util import mkpath

# =============================================================================
# Find the top of the source tree and set the search path accordingly
# =============================================================================

BINARY_KIT_VERSION = open("binary_kit_version").read().strip()
BKIT_DIR = os.path.join(os.getcwd(), "miro-binary-kit-osx-%s" % BINARY_KIT_VERSION)

if not os.path.exists(BKIT_DIR) or not os.path.isdir(BKIT_DIR):
    print "Binary kit %s is missing.  Run 'setup_binarykit.sh'." % BKIT_DIR
    sys.exit(1)

ROOT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
ROOT_DIR = os.path.join(ROOT_DIR, '..')
ROOT_DIR = os.path.normpath(ROOT_DIR)

PORTABLE_DIR = os.path.join(ROOT_DIR, 'lib')
PLATFORM_DIR = os.path.join(ROOT_DIR, 'osx')
PLATFORM_PACKAGE_DIR = os.path.join(PLATFORM_DIR, 'plat')

PYTHON_VERSION = sys.version[0:3]

SANDBOX_ROOT_DIR = os.path.normpath(os.path.normpath(os.path.join(ROOT_DIR, '..')))
SANDBOX_DIR = os.path.join(SANDBOX_ROOT_DIR, 'sandbox_%s' % BINARY_KIT_VERSION)
PYTHON_ROOT = os.path.join(SANDBOX_DIR, "Frameworks", "Python.framework", "Versions", PYTHON_VERSION)
PYTHON_LIB = os.path.join(PYTHON_ROOT, "Python")

# =============================================================================
# Drop out if the current binary kit isn't downloaded.
# =============================================================================

if not os.path.exists(BKIT_DIR):
    print "Binary kit %s is not installed." % BKIT_DIR
    print "Run setup_sandbox.sh."
    sys.exit(1)

# =============================================================================
# Only now may we import things from the local sandbox and our own tree
# =============================================================================

import py2app
from py2app.build_app import py2app
from distutils.extension import Extension
from distutils.cmd import Command
from distutils.errors import DistutilsFileError

# when we install the portable modules, they will be in the miro package, but
# at this point, they are in a package named "lib", so let's hack it
sys.path.append(ROOT_DIR)
import lib
sys.modules['miro'] = lib

from miro import util

# =============================================================================
# Utility function used to extract stuff from the binary kit
# =============================================================================

def copy_binaries(source, target, binaries):
    mkpath(target)
    for mem in binaries:
        copy_file(os.path.join(BKIT_DIR, source, mem), target, update=True)

def extract_binaries(source, target, force=True):
    if force and os.path.exists(target):
        shutil.rmtree(target, True)

    if os.path.exists(target):
        print "    (all skipped, already there)"
        return

    if not os.path.exists(target):
        os.makedirs(target)

    rootpath = os.path.join(BKIT_DIR, source)
    binaries = glob(os.path.join(rootpath, '*.tar.gz'))

    if len(binaries) == 0:
        print "    (all skipped, not found in binary kit)"
        return

    for binary in binaries:
        tar = tarfile.open(binary, 'r:gz')
        try:
            for member in tar.getmembers():
                if os.path.basename(member.name) not in ('._Icon\r', 'Icon\r'):
                    tar.extract(member, target)
        finally:
            tar.close()

# =============================================================================
# A theme archive file
# =============================================================================

class Config (object):
    
    def __init__(self, path, themePath=None):
        self.config = util.read_simple_config_file(path)
        self.themeDir = os.path.join(ROOT_DIR, 'osx', 'build', 'theme')
        self.themeConfig = None
        if themePath is not None:
            self.extract_theme_content(themePath, self.themeDir)
            themeConfigPath = os.path.join(self.themeDir, "app.config")
            self.themeConfig = util.read_simple_config_file(themeConfigPath)
        elif os.path.exists(self.themeDir):
            shutil.rmtree(self.themeDir)
        
    def extract_theme_content(self, themePath, target):
        if os.path.exists(target):
            shutil.rmtree(target)
        
        os.makedirs(target)
        excludeList = ["xul"]
        themeArchive = zipfile.ZipFile(themePath, "r")
        for entry in themeArchive.namelist():
            extract = True
            for excluded in excludeList:
                if entry.startswith(excluded):
                    extract = False
                    break            
            if extract:
                path = os.path.join(target, entry)
                if entry.endswith('/'):
                    os.makedirs(path)
                else:
                    data = themeArchive.read(entry)
                    f = open(path, "wt")
                    f.write(data)
                    f.close()
        themeArchive.close()
    
    def get_icon_file(self):
        iconFile = None
        if self.themeConfig is not None:
            themeIconFile = self.themeConfig.get('iconFile-osx')
            if themeIconFile is not None:
                iconFile = os.path.join(self.themeDir, themeIconFile)
        if iconFile is None:
            iconFile = os.path.join(ROOT_DIR, 'osx', '%s.icns' % self.config.get('shortAppName'))
        return iconFile
        
    def get_data(self, mergeThemeData=True):
        if self.themeConfig is None or not mergeThemeData:
            return self.config
        else:
            conf = self.config.copy()
            conf.update(self.themeConfig)
            return conf
    
    def get(self, key, prioritizeTheme=True):
        if self.themeConfig is not None and key in self.themeConfig and prioritizeTheme:
            return self.themeConfig[key]
        else:
            return self.config.get(key)

# =============================================================================
# Define our custom build task
# =============================================================================

class MiroBuild (py2app):

    description = "create the OS X Miro application"
    
    user_options = py2app.user_options + [
        ("keep-tests",   "u", "keep the unit tests module"),
        ("make-dmg",     "d", "produce a disk image"),
        ("force-update", "f", "force resource update"),
        ("theme=",       "t", "theme file to use")]

    boolean_options = py2app.boolean_options + ["make-dmg", "force-update", "keep-tests"]
        
    def initialize_options(self):
        self.keep_tests = False
        self.make_dmg = False
        self.force_update = False
        self.theme = None
        py2app.initialize_options(self)
        
    def finalize_options(self):
        py2app.finalize_options(self)
        self.setup_config()
        self.setup_distribution()
        self.setup_options()

    def setup_config(self):
        # Get revision information.
        revision = util.query_revision()
        if revision is None:
            revisionURL = 'unknown'
            revisionNum = '0000'
            revision = 'unknown'
        else:
            revisionURL, revisionNum = revision
            revision = '%s - %s' % revision

        # Inject the revision number into app.config.template to get app.config.
        appConfigTemplatePath = os.path.join(ROOT_DIR, 'resources/app.config.template')
        self.appConfigPath = os.path.join(ROOT_DIR, 'resources/app.config')
        
        self.fillTemplate(appConfigTemplatePath,
                          self.appConfigPath,
                          BUILD_MACHINE="%s@%s" % (os.getlogin(),
                                                   os.uname()[1]),
                          BUILD_TIME=str(time.time()),
                          APP_REVISION = revision, 
                          APP_REVISION_URL = revisionURL, 
                          APP_REVISION_NUM = revisionNum, 
                          APP_PLATFORM = 'osx')

        if self.theme is not None:
            if not os.path.exists(self.theme):
                raise DistutilsFileError, "theme file %s not found" % self.theme
            else:
                print "Using theme %s" % self.theme

        self.config = Config(self.appConfigPath, self.theme)
    
    def setup_distribution(self):
        self.distribution.app = ['Miro.py']
        self.distribution.ext_modules = list()
        self.distribution.ext_modules.append(self.get_idletime_ext())
        self.distribution.ext_modules.append(self.get_keychain_ext())
        self.distribution.ext_modules.append(self.get_qtcomp_ext())
        self.distribution.ext_modules.append(self.get_growl_ext())
        self.distribution.ext_modules.append(self.get_growl_image_ext())
        self.distribution.ext_modules.append(self.get_fasttypes_ext())
        self.distribution.ext_modules.append(self.get_ngrams_ext())

        self.distribution.packages = [
            'miro',
            'miro.dl_daemon',
            'miro.dl_daemon.private',
            'miro.frontends',
            'miro.frontends.cli',
            'miro.frontends.profilewidgets',
            'miro.frontends.shell',
            'miro.frontends.widgets',
            'miro.extensions',
            'miro.plat',
            'miro.plat.frontends',
            'miro.plat.frontends.widgets'
        ]

        if self.keep_tests:
            self.distribution.packages.append('miro.test')

        self.distribution.package_dir = {
            'miro': PORTABLE_DIR,
            'miro.plat': PLATFORM_PACKAGE_DIR,
        }
        
        self.iconfile = self.config.get_icon_file()
        
        excludedResources = ['.svn', '.DS_Store']
        self.resources = [
            os.path.join('Resources-Widgets', 'MainMenu.nib'),
            os.path.join('Resources-Widgets', 'OverlayPalette.nib'),
            os.path.join('Resources-Widgets', 'Credits.html'),
            'qt_extractor.py'
        ]
        self.resources.extend(glob(os.path.join('Resources-Widgets', '*.png')))
        self.resources.extend(glob(os.path.join('Resources-Widgets', 'warmup.mov')))
    
    def setup_options(self):
        self.bundleRoot = os.path.join(self.dist_dir, '%s.app/Contents' % self.config.get('shortAppName'))
        self.rsrcRoot = os.path.join(self.bundleRoot, 'Resources')
        self.fmwkRoot = os.path.join(self.bundleRoot, 'Frameworks')
        self.cmpntRoot = os.path.join(self.bundleRoot, 'Components')
        self.helpersRoot = os.path.join(self.bundleRoot, 'Helpers')
        self.prsrcRoot = os.path.join(self.rsrcRoot, 'resources')
        
    def get_idletime_ext(self):
        idletime_src = glob(os.path.join(ROOT_DIR, 'osx', 'modules', 'idletime.c'))
        idletime_link_args = ['-framework', 'CoreFoundation', '-framework', 'IOKit']
        return Extension("miro.plat.idletime", sources=idletime_src, extra_link_args=idletime_link_args)
    
    def get_keychain_ext(self):
        keychain_src = glob(os.path.join(ROOT_DIR, 'osx', 'modules', 'keychain.c'))
        keychain_link_args = ['-framework', 'Security']
        return Extension("miro.plat.keychain", sources=keychain_src, extra_link_args=keychain_link_args)
    
    def get_qtcomp_ext(self):
        qtcomp_src = glob(os.path.join(ROOT_DIR, 'osx', 'modules', 'qtcomp.c'))
        qtcomp_link_args = ['-framework', 'CoreFoundation', '-framework', 'CoreServices', '-framework', 'QuickTime']
        return Extension("miro.plat.qtcomp", sources=qtcomp_src, extra_link_args=qtcomp_link_args)
    
    def get_growl_ext(self):
        growl_src = glob(os.path.join(ROOT_DIR, 'osx', 'modules', '_growl.c'))
        growl_link_args = ['-framework', 'CoreFoundation']
        return Extension("miro.plat._growl", sources=growl_src, extra_link_args=growl_link_args)
    
    def get_growl_image_ext(self):
        growl_image_src = glob(os.path.join(ROOT_DIR, 'osx', 'modules', '_growlImage.m'))
        growl_image_link_args = ['-framework', 'Cocoa']
        return Extension("miro.plat._growlImage", sources=growl_image_src, extra_link_args=growl_image_link_args)
    
    def get_fasttypes_ext(self):
        return Extension("miro.fasttypes",
                [os.path.join(PORTABLE_DIR, 'fasttypes.c')])

    def get_ngrams_ext(self):
        return Extension("miro.ngrams",
                [os.path.join(PORTABLE_DIR, 'ngrams.c')])
    
    def fillTemplate(self, templatepath, outpath, **vars):
        s = open(templatepath, 'rt').read()
        s = string.Template(s).safe_substitute(**vars)
        f = open(outpath, "wt")
        f.write(s)
        f.close()
    
    def run(self):
        print "Building %s v%s (%s)" % (self.config.get('longAppName'), self.config.get('appVersion'), self.config.get('appRevision'))
        
        self.setup_info_plist()

        py2app.run(self)
        
        self.fix_frameworks_alias()
        self.precompile_site_pyc()
        self.copy_quicktime_components()
        self.copy_conversion_helpers()
        self.copy_ffmpeg_presets()
        self.copy_portable_resources()
        self.copy_config_file()
        self.copy_localization_files()
        if self.theme is not None:
            self.copy_theme_files()
        if not self.alias:
            self.relocate_python_executable()
            self.fix_install_names()
        
        self.clean_up_incomplete_lproj()
        self.clean_up_unwanted_data()

        if self.make_dmg:
            self.make_disk_image()
    
    def setup_info_plist(self):
        def updatePListEntry(plist, key, conf, prioritizeTheme=True):
            entry = plist[key]
            plist[key] = string.Template(entry).safe_substitute(conf.get_data(prioritizeTheme))

        infoPlist = plistlib.readPlist(u'Info.plist')
        updatePListEntry(infoPlist, u'CFBundleGetInfoString', self.config)
        updatePListEntry(infoPlist, u'CFBundleIdentifier', self.config, False)
        updatePListEntry(infoPlist, u'CFBundleExecutable', self.config, False)
        updatePListEntry(infoPlist, u'CFBundleName', self.config)
        updatePListEntry(infoPlist, u'CFBundleShortVersionString', self.config)
        updatePListEntry(infoPlist, u'CFBundleVersion', self.config)
        updatePListEntry(infoPlist, u'NSHumanReadableCopyright', self.config)

        infoPlist['CFBundleDevelopmentRegion'] = 'en'
        infoPlist['CFBundleAllowMixedLocalizations'] = True
        infoPlist['CFBundleLocalizations'] = self.get_localizations_list()
        
        if not self.alias:
            infoPlist['PyExecutableName'] = os.path.join("@executable_path", "..", "Frameworks", "Python.framework", "Versions", PYTHON_VERSION, "bin", "python")
        
        self.plist = infoPlist

    def _get_app_root(self):
        dist_app = os.path.join("dist", "Miro.app")
        if os.path.exists(dist_app):
            return dist_app
        return "Miro.app"

    def relocate_python_executable(self):
        # In certain unknown circumstances, Mac OS will launch the embedded
        # python executable instead of the Miro executable when the application
        # is double clicked in the Finder, and since OS X LaunchServices pass
        # a -psn_X_Y parameter representing the process serial number which
        # python does not understand, bad things happen, as described in #13120.
        # There is currently zero clue as to why this happens, but the workaround
        # is simply to move the python executable to another location in the 
        # application bundle, which prevents OS X to pick it as the main executable.
        # (This also requires to add the PyExecutableName entry to the Info.plist, 
        # which is done in setup_info_plist above).
        
        print "Relocating python executable"
        app_root = self._get_app_root()
        source = os.path.join(app_root, "Contents", "MacOS", "python")
        target = os.path.join(app_root, "Contents", "Frameworks", "Python.framework", "Versions", PYTHON_VERSION, "bin")
        if not os.path.exists(target):
            os.mkdir(target)
        shutil.move(source, target)

        # Note that we obviously also need to update the executable install name.
        
        py_exe = os.path.join(target, "python")
        old_install_name = os.path.join("@executable_path", "..", "Frameworks", "Python.framework", "Versions", PYTHON_VERSION, "Python")
        new_install_name = os.path.join("@executable_path", "..", "Python")
        os.system('install_name_tool -change %s %s %s' % (old_install_name, new_install_name, py_exe))

    def fix_install_names(self):
        py_install_name = os.path.join("@executable_path", "..", "Frameworks", "Python.framework", "Versions", PYTHON_VERSION, "Python")
        app_root = self._get_app_root()

        fasttypes_mod = os.path.join(app_root, "Contents", "Resources", "lib", "python%s" % PYTHON_VERSION, "lib-dynload", "miro", "fasttypes.so")
        os.system('install_name_tool -change %s %s %s' % (PYTHON_LIB, py_install_name, fasttypes_mod))

        libtorrent_so = os.path.join(app_root, "Contents", "Resources", "lib", "python%s" % PYTHON_VERSION, "lib-dynload", "libtorrent.so")
        os.system('install_name_tool -change %s %s %s' % (PYTHON_LIB, py_install_name, libtorrent_so))

    def fix_frameworks_alias(self):
        # Py2App seems to have a bug where alias builds would get 
        # incorrect symlinks to frameworks, so create them manually. 
        for fmwk in glob(os.path.join(self.fmwkRoot, '*.framework')): 
            if os.path.islink(fmwk): 
                dest = os.readlink(fmwk) 
                if not os.path.exists(dest): 
                    print "Fixing incorrect symlink for %s" % os.path.basename(fmwk) 
                    os.remove(fmwk) 
                    os.symlink(os.path.dirname(dest), fmwk)

    def copy_quicktime_components(self):
        print 'Copying QuickTime components to application bundle'
        extract_binaries('qtcomponents', self.cmpntRoot, self.force_update)

    def copy_conversion_helpers(self):
        print 'Copying video conversion helpers to application bundle'
        copy_binaries('ffmpeg/bin/', self.helpersRoot, ["ffmpeg"])
        copy_binaries('ffmpeg2theora/bin/', self.helpersRoot, ["ffmpeg2theora"])

    def copy_ffmpeg_presets(self):
        preset_source_dir = os.path.join(BKIT_DIR, 'ffmpeg', 'presets')
        preset_dest_dir = os.path.join(self.rsrcRoot, 'ffmpeg-presets')
        preset_list = os.listdir(preset_source_dir)
        copy_binaries('ffmpeg/presets/', preset_dest_dir, preset_list)

    def copy_portable_resources(self):
        print "Copying portable resources to application bundle"

        if self.force_update and os.path.exists(self.prsrcRoot):
            shutil.rmtree(self.prsrcRoot, True)

        if not os.path.exists(self.prsrcRoot):
            os.mkdir(self.prsrcRoot)

        resources = ['searchengines', 'images', 'conversions', 'devices']
        if self.keep_tests:
            resources.append('testdata')

        for resource in resources:
            src = os.path.join(ROOT_DIR, 'resources', resource)
            rsrcName = os.path.basename(src)
            if os.path.isdir(src):
                dest = os.path.join(self.prsrcRoot, rsrcName)
                copy = shutil.copytree
            else:
                dest = os.path.join(self.prsrcRoot, rsrcName)
                copy = shutil.copy
            if os.path.exists(dest):
                print "    (%s skipped, already bundled)" % resource
            else:
                print "    %s" % dest
                copy(src, dest)

    def copy_config_file(self):
        print "Copying config file to application bundle"
        shutil.move(self.appConfigPath, os.path.join(self.prsrcRoot, 'app.config'))

    def get_localizations_list(self):
        localeDir = os.path.join(ROOT_DIR, 'resources', 'locale')
        entries = os.listdir(localeDir)
        localizations = list()
        for e in entries:
            if e.endswith('.po'):
                localizations.append(os.path.splitext(e)[0])
        return localizations

    def copy_localization_files(self):
        # Copy the gettext MO files in a 'locale' folder inside the
        # application bundle resources folder. Doing this manually at
        # this stage instead of automatically through the py2app
        # options allows to avoid having an intermediate unversioned
        # 'locale' folder.
        print "Copying gettext MO files to application bundle"

        localeDir = os.path.join(ROOT_DIR, 'resources', 'locale')
        lclDir = os.path.join(self.rsrcRoot, 'locale')
        if self.force_update and os.path.exists(lclDir):
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
    
    def precompile_site_pyc(self):
        print "Pre-compiling site.py"
        import py_compile
        py_compile.compile(os.path.join(self.rsrcRoot, 'lib', 'python%s' % PYTHON_VERSION, 'site.py'))
    
    def copy_theme_files(self):
        # Copy theme files to the application bundle
        print "Copying theme file"
        
        sourceDir = self.config.themeDir
        targetDir = os.path.join(self.bundleRoot, "Theme", self.config.get("themeName"))

        if self.force_update and os.path.exists(targetDir):
            shutil.rmtree(targetDir, True);

        if os.path.exists(targetDir):
            print "    (all skipped, already bundled)"
        else:
            os.makedirs(targetDir)
            def copyDirectory(d):
                for f in glob(os.path.join(d, "*")):
                    dest = os.path.join(targetDir, f[len(sourceDir)+1:])
                    print "    %s" % dest
                    if os.path.isfile(f):
                        shutil.copy(f, dest)
                    elif os.path.isdir(f):
                        os.makedirs(dest)
                        copyDirectory(f)
            copyDirectory(sourceDir)
    
    def clean_up_incomplete_lproj(self):
        print "Wiping out incomplete lproj folders"
        
        incompleteLprojs = list()
        for lproj in glob(os.path.join(self.rsrcRoot, '*.lproj')):
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
        
    def clean_up_unwanted_data(self):
        """docstring for clean_up_unwanted_data"""
        pass
        # Check that we haven't left some turds in the application bundle.
        
        excluded_folders = ['.svn']
        if not self.keep_tests:
            excluded_folders.append('test')
        
        wipeList = list()
        for root, dirs, files in os.walk(os.path.join(self.dist_dir, '%s.app' % self.config.get('shortAppName'))):
            for excluded in excluded_folders:
                if excluded in dirs:
                    dirs.remove(excluded)
                    wipeList.append(os.path.join(root, excluded))
            for excluded in ('.DS_Store', 'info.nib', 'classes.nib'):
                if excluded in files:
                    wipeList.append(os.path.join(root, excluded))
        
        if len(wipeList) > 0:
            print "Wiping out unwanted data from the application bundle."
            for item in wipeList:
                print "    %s" % item
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)

    def make_disk_image(self):
        print "Building disk image..."

        imgName = "%s-%4d-%02d-%02d.dmg" % (
            self.config.get('shortAppName'),
            datetime.date.today().year,
            datetime.date.today().month,
            datetime.date.today().day)

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

        os.rename(os.path.join(self.dist_dir,"%s.app" % self.config.get('shortAppName')),
                  os.path.join(imgDirName, "%s.app" % self.config.get('shortAppName')))
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

        os.system("hdiutil create -srcfolder \"%s\" -volname \"%s\" -format UDZO \"%s\"" %
                  (imgDirName,
	       self.config.get('shortAppName'),
                   os.path.join(self.dist_dir, "%s.tmp.dmg" % self.config.get('shortAppName'))))

        os.system("hdiutil convert -format UDZO -imagekey zlib-level=9 -o \"%s\" \"%s\"" %
                  (imgPath,
                   os.path.join(self.dist_dir, "%s.tmp.dmg" % self.config.get('shortAppName'))))
                  
        os.remove(os.path.join(self.dist_dir,"%s.tmp.dmg" % self.config.get('shortAppName')))

        print "Completed"
        os.system("ls -la \"%s\"" % imgPath)

# =============================================================================
# Define the clean task
# =============================================================================

class MiroClean (Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

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
            for appl in glob("*.app"):
                shutil.rmtree(appl)
        except:
            pass

if __name__ == "__main__":
    # =========================================================================
    # This is weird, if we do this from the MiroBuild command we eventually get
    # an error in the macholib module... So let's just do it here.
    # =========================================================================

    print 'Extracting frameworks to build directory...'
    frameworks_path = os.path.join(ROOT_DIR, 'osx/build/frameworks')
    extract_binaries('frameworks', frameworks_path, True)
    frameworks = glob(os.path.join(frameworks_path, '*.framework'))

    # =========================================================================
    # Launch the setup process...
    # =========================================================================

    from Pyrex.Distutils import build_ext
    from distutils.core import setup

    setup( cmdclass = {'build_ext': build_ext, 'clean': MiroClean,
                       'py2app': MiroBuild},
           options  = {'py2app':{'frameworks': frameworks}} )
