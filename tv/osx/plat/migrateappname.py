# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
        
        from miro import app
        from miro import prefs
        videoDir = app.config.get(prefs.MOVIES_DIRECTORY)
        if videoDir == newDefault:
            app.controller.changeMoviesDirectory(newDefault, True)
