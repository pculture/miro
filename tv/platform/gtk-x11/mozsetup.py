"""Functions to assist in seting up the DTV mozilla environment."""

import os
import config
import gtkmozembed

def createProfileDirectory():
    """Create the mozilla profile directory, if needed."""

    path = os.path.join(config.get(config.SUPPORT_DIRECTORY), 'mozilla')
    if not os.path.exists(path):
        os.makedirs(path)

def createPrefsJS():
    """Create the file prefs.js in the mozilla profile directory.  This
    file does things like turn off the warning when navigating to https pages.
    """

    prefsContent = """\
# Mozilla User Preferences
user_pref("security.warn_entering_secure", false);
user_pref("security.warn_leaving_secure", false);
user_pref("security.warn_leaving_secure.show_once", false);
"""
    prefsPath = os.path.join(config.get(config.SUPPORT_DIRECTORY), 'mozilla',
            'prefs.js')
    if not os.path.exists(prefsPath):
        f = open(prefsPath, "wt")
        f.write(prefsContent)
        f.close()

def setupMozillaEnvironment():
    """Do all the work nessecary setup the DTV Mozilla environment."""
    createProfileDirectory()
    createPrefsJS()

    # newer versions of gtkmozembed use gtkmozembed.set_profile_path(), older
    # versions have the awkward name
    # gtkmozembed.gtk_moz_embed_set_profile_path()
    if hasattr(gtkmozembed, 'set_profile_path'):
        set_profile_path = gtkmozembed.set_profile_path
    else:
        set_profile_path = gtkmozembed.gtk_moz_embed_set_profile_path
        
    set_profile_path(config.get(config.SUPPORT_DIRECTORY), 'mozilla')
