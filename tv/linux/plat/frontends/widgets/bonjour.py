# Miro - an RSS based video player application
# Copyright (C) 2008, 2009, 2010, 2011
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
import logging

from miro import app
from miro import prefs
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs

def check_bonjour_install():
    request_count = app.config.get(prefs.BONJOUR_REQUEST_COUNT)
    if app.sharing_manager.mdns_present or request_count > 0:
        return
    install_bonjour(startup=True)

# We can't really do much here ...
def install_bonjour(startup=False):
    title = _("Install Bonjour")
    rawtext = ('For the best %(appname)s experience, we suggest you '
               'install Bonjour.  Installing Bonjour will '
               'allow you share your media library with other '
               '%(appname)s users on your network, as well as stream '
               'media from other %(appname)s users on your network.\n\n'
               '%(appname)s has determined that your system is most '
               'likely missing the Avahi mDNSResponder compatibility '
               'library.  Please refer to your operating system '
               'documentation on how you can install this library.' %
               {"appname": app.config.get(prefs.SHORT_APP_NAME)}
              )
    if startup:
        rawtext += ('\n\nWould you like %(appname)s to warn you on next '
                   'startup?' % 
                   {"appname": app.config.get(prefs.SHORT_APP_NAME)}
                  )
    description = _(rawtext)
    if not startup:
        dialogs.show_message(title, description)
    else:
        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_YES,
                                          dialogs.BUTTON_NO
                                         ])
        if ret is None or ret == dialogs.BUTTON_YES:
            return
        else:
            app.config.set(prefs.BONJOUR_REQUEST_COUNT, 1)

