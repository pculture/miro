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

def migrateSupport(oldAppName, newAppName):
    print('Checking Miro preferences and support migration...')

    global migrated
    migrated = False

    from AppKit import NSBundle

    prefsPath = os.path.expanduser('~/Library/Preferences')
    newDomain = NSBundle.mainBundle().bundleIdentifier()
    newPrefs = '%s.plist' % os.path.join(prefsPath, newDomain)
    oldDomain = newDomain.replace(newAppName, oldAppName)
    oldPrefs = '%s.plist' % os.path.join(prefsPath, oldDomain)
    
    if os.path.exists(oldPrefs):
        if os.path.exists(newPrefs):
            print("Both %s and %s preference files exist." % (oldAppName, newAppName))
        else:
            os.rename(oldPrefs, newPrefs)
            print("Migrated preferences to %s" % newPrefs)

    supportFolderRoot = os.path.expanduser('~/Library/Application Support')
    oldSupportFolder = os.path.join(supportFolderRoot, oldAppName)
    newSupportFolder = os.path.join(supportFolderRoot, newAppName)
    if os.path.exists(oldSupportFolder):
        if os.path.exists(newSupportFolder):
            print("Both %s and %s support folders exist." % (oldAppName, newAppName))
        else:
            os.rename(oldSupportFolder, newSupportFolder)
            print("Migrated support folder to %s" % newSupportFolder)
            migrated = True


def migrateVideos(oldAppName, newAppName):
    import logging
    logging.debug('Checking Miro videos migration...')

    global migrated
    if migrated:
        moviesRootFolder = os.path.expanduser('~/Movies')
        oldDefault = os.path.join(moviesRootFolder, oldAppName)
        newDefault = os.path.join(moviesRootFolder, newAppName)
        
        import config
        import prefs
        videoDir = config.get(prefs.MOVIES_DIRECTORY)
        if videoDir == newDefault:
            import app
            app.controller.changeMoviesDirectory(newDefault, True)
