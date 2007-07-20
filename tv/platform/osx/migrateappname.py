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
            from app import changeMoviesDirectory
            changeMoviesDirectory(newDefault, True)
