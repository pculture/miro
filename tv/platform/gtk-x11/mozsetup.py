# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

"""Functions to assist in seting up the DTV mozilla environment."""

import os
import config
import prefs
import gtkmozembed
from frontend_implementation.gtk_queue import gtkAsyncMethod

def createProfileDirectory():
    """Create the mozilla profile directory, if needed."""

    path = os.path.join(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla')
    if not os.path.exists(path):
        os.makedirs(path)

def createPrefsJS():
    """Create the file prefs.js in the mozilla profile directory.  This
    file does things like turn off the warning when navigating to https pages.
    """

    prefsContent = """\
# Mozilla User Preferences
user_pref("security.warn_entering_secure", false);
user_pref("security.warn_entering_weak", false);
user_pref("security.warn_leaving_secure", false);
user_pref("security.warn_submit_insecure", false);
user_pref("general.useragent.vendor", %s);
user_pref("general.useragent.vendorSub", %s);
user_pref("general.useragent.vendorComment", %s);

""" % (repr(config.get(prefs.LONG_APP_NAME)),
       repr(config.get(prefs.APP_VERSION)),
       repr(config.get(prefs.PROJECT_URL)))
    prefsPath = os.path.join(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla',
            'prefs.js')
    f = open(prefsPath, "wt")
    f.write(prefsContent)
    f.close()

@gtkAsyncMethod
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
        
    set_profile_path(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla')
