# Miro - an RSS based video player application
# Copyright (C) 2008 Participatory Culture Foundation
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

import os, os.path, sys
import subprocess, time
from miro import app, httpclient, dialogs, config, prefs, signals
from miro.gtcache import gettext as _
from miro.platform import specialfolders, resources
from xpcom import shutdown
import tempfile
import webbrowser

FLASH_INSTALL_URL = 'http://fpdownload.macromedia.com/get/flashplayer/current/install_flash_player.exe'
FLASH_EULA_URL = 'http://www.adobe.com/products/eulas/players/flash/'

def restartMiro(obj=None):
    root = resources.appRoot().encode('mbcs')
    args = [sys.executable, os.path.join(root, 'application.ini')]
    theme = config.get(prefs.THEME_NAME)
    if theme is not None:
        args += ['--theme', '"%s"' % theme]
    os.chdir(root)
    os.execv(sys.executable, args)

    
def isFlashInstalled():
    return os.path.exists(os.path.join(
            specialfolders.getSpecialFolder('System'),
            'Macromed', 'Flash', 'flashplayer.xpt'))


def installFlash():
    def httpSuccess(info):
        fd, filename = tempfile.mkstemp(suffix='.exe')
        output = os.fdopen(fd, 'wb')
        output.write(info['body'])
        output.close()
        code = subprocess.call([filename, '/S'])
        os.unlink(filename)
        if code: # fail!
            print 'error installing flash'
            config.set(prefs.FLASH_REQUEST_COUNT, 0)
        else:
            try:
                webbrowser.open(FLASH_EULA_URL)
            except WindowsError, e:
                if e.errno != 22:
                    raise
                # Application not found
                # fake it by calling explorer
                os.system("explorer %s" % FLASH_EULA_URL)

            title = _("Restart %s?") % config.get(prefs.SHORT_APP_NAME)
            description = _("To enable the Flash plugin, %s needs to be restarted.  Click Yes to shut %s down, or No to do it later.")
            description = description % (config.get(prefs.SHORT_APP_NAME),
                                         config.get(prefs.SHORT_APP_NAME))
            
            dialog = dialogs.ChoiceDialog(title, description,
                                          dialogs.BUTTON_YES,
                                          dialogs.BUTTON_NO)

            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_YES:
                    app.controller.shutdown()
                    shutdown._handlers[:1] = [(restartMiro, (), {})]
                    
            dialog.run(callback)

                
    def httpFailure(error):
        print 'error downloading flash', error
        config.set(prefs.FLASH_REQUEST_COUNT, 0)
    httpclient.grabURL(FLASH_INSTALL_URL, httpSuccess, httpFailure)

def checkFlashInstall():
    request_count = config.get(prefs.FLASH_REQUEST_COUNT)
    if isFlashInstalled() or request_count > 0:
        return

    title = _("Install Flash?")
    description = _("For the best %s experience, you should install Adobe Flash.  Do this now?")
    description = description % config.get(prefs.SHORT_APP_NAME)

    dialog = dialogs.ThreeChoiceDialog(title, description,
                                       dialogs.BUTTON_YES,
                                       dialogs.BUTTON_NOT_NOW,
                                       dialogs.BUTTON_NO)
    
    def callback(dialog):
        if dialog.choice is None or dialog.choice == dialogs.BUTTON_NOT_NOW:
            return
        if dialog.choice == dialogs.BUTTON_YES:
            installFlash()
        else:
            config.set(prefs.FLASH_REQUEST_COUNT, 1)

    dialog.run(callback)
