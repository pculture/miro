# Miro - an RSS based video player application
# Copyright (C) 2008-2009 Participatory Culture Foundation
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
from miro import config
from miro import prefs
from miro.gtcache import gettext as _
from miro.plat import specialfolders
from miro.frontends.widgets import dialogs

FLASH_URL = "http://get.adobe.com/flashplayer/"

def _is_flash_installed():
    logging.info("checking %s", os.path.join(
            specialfolders.get_special_folder('System'),
            'Macromed', 'Flash', 'flashplayer.xpt'))
    return os.path.exists(os.path.join(
            specialfolders.get_special_folder('System'),
            'Macromed', 'Flash', 'flashplayer.xpt'))

def check_flash_install():
    request_count = config.get(prefs.FLASH_REQUEST_COUNT)
    if _is_flash_installed() or request_count > 0:
        return

    title = _("Install Adobe Flash?")
    description = _(
        "For the best %(appname)s experience, we suggest you install Adobe Flash.  Would you "
        "like to do this now?",
        {"appname": config.get(prefs.SHORT_APP_NAME)}
    )

    ret = dialogs.show_choice_dialog(title, description,
            [dialogs.BUTTON_YES, dialogs.BUTTON_NOT_NOW, dialogs.BUTTON_NO])

    if ret is None or ret == dialogs.BUTTON_NOT_NOW:
        return

    elif ret == dialogs.BUTTON_YES:
        app.widgetapp.open_url(FLASH_URL)
        title = _("Install Adobe Flash")
        description = _(
            "Your browser will load the web-site where you can download and install "
            "Adobe Flash.\n"
            "\n"
            "You should quit %(appname)s now and start it up again after Adobe Flash has "
            "been installed.",
            {"appname": config.get(prefs.SHORT_APP_NAME)}
        )
        dialogs.show_message(title, description)

    else:
        config.set(prefs.FLASH_REQUEST_COUNT, 1)
