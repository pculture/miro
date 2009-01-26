# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""Functions to assist in seting up the DTV mozilla environment."""

import os
from miro import config
from miro import prefs
import gtkmozembed

def create_profile_directory():
    """Create the mozilla profile directory, if needed."""

    path = os.path.join(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla')
    if not os.path.exists(path):
        os.makedirs(path)

def create_prefs_js():
    """Create the file prefs.js in the mozilla profile directory.  This
    file does things like turn off the warning when navigating to https pages.
    """

    prefs_content = """\
# Mozilla User Preferences
user_pref("security.warn_entering_secure", false);
user_pref("security.warn_entering_weak", false);
user_pref("security.warn_viewing_mixed", false);
user_pref("security.warn_leaving_secure", false);
user_pref("security.warn_submit_insecure", false);
user_pref("security.warn_entering_secure.show_once", false);
user_pref("security.warn_entering_weak.show_once", false);
user_pref("security.warn_viewing_mixed.show_once", false);
user_pref("security.warn_leaving_secure.show_once", false);
user_pref("security.warn_submit_insecure.show_once", false);
user_pref("security.enable_java", false);
user_pref("browser.xul.error_pages.enabled", false);
user_pref("general.useragent.vendor", %s);
user_pref("general.useragent.vendorSub", %s);
user_pref("general.useragent.vendorComment", %s);
user_pref("capability.principal.codebase.p0.granted", "UniversalBrowserWrite UniversalBrowserRead"); 
user_pref("capability.principal.codebase.p0.id", "file://"); 
user_pref("capability.principal.codebase.p0.subjectName", "") 
""" % (repr(config.get(prefs.LONG_APP_NAME)),
       repr(config.get(prefs.APP_VERSION)),
       repr(config.get(prefs.PROJECT_URL)))

    if config.get(prefs.HTTP_PROXY_ACTIVE):
        prefs_content += """\
user_pref("network.proxy.type", 1);
user_pref("network.proxy.http", %s);
user_pref("network.proxy.http_port", %d);
user_pref("network.proxy.ssl", %s);
user_pref("network.proxy.ssl_port", %d);
user_pref("network.proxy.share_proxy_settings", true);
""" % (repr(str(config.get(prefs.HTTP_PROXY_HOST))),
       config.get(prefs.HTTP_PROXY_PORT),
       repr(str(config.get(prefs.HTTP_PROXY_HOST))),
       config.get(prefs.HTTP_PROXY_PORT))
       


    prefs_path = os.path.join(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla', 'prefs.js')
    f = open(prefs_path, "wt")
    f.write(prefs_content)
    f.close()

def setup_mozilla_environment():
    """Do all the work necessary setup the Miro Mozilla environment."""
    create_profile_directory()
    create_prefs_js()

    # newer versions of gtkmozembed use gtkmozembed.set_profile_path(), older
    # versions have the awkward name
    # gtkmozembed.gtk_moz_embed_set_profile_path()
    if hasattr(gtkmozembed, 'set_profile_path'):
        set_profile_path = gtkmozembed.set_profile_path
    else:
        set_profile_path = gtkmozembed.gtk_moz_embed_set_profile_path
    set_profile_path(config.get(prefs.SUPPORT_DIRECTORY), 'mozilla')

    # prefer set_path to set_comp_path
    if hasattr(gtkmozembed, 'set_path'):
        set_comp_path = gtkmozembed.set_path
    elif hasattr(gtkmozembed, 'set_comp_path'):
        set_comp_path = gtkmozembed.set_comp_path
    else:
        set_comp_path = None

    if set_comp_path:
        set_comp_path(config.get(prefs.MOZILLA_LIB_PATH))
