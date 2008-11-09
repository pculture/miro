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

import os, sys
import subprocess
from miro import app, httpclient, dialogs, config, prefs
from miro.gtcache import gettext as _
from miro.plat import specialfolders, resources
from xpcom import shutdown
import tempfile
import webbrowser

FLASH_INSTALL_URL = 'http://fpdownload.macromedia.com/get/flashplayer/current/install_flash_player.exe'
FLASH_EULA_URL = 'http://www.adobe.com/products/eulas/players/flash/'

if sys.version_info < (2, 5, 1):
    # monkeypatch webbrowser.BackgroundBrowser.open
    # the version in 2.5.0 doesn't correctly handle Popen on Windows.
    # XXX: when we switch the build process to 2.5.1, this can be removed.
    # fixes #10020
    def patchedOpen(self, url, new=0, autoraise=1):
        cmdline = [self.name] + [arg.replace('%s', url) for arg
                                 in self.args]
        try:
            p = subprocess.Popen(cmdline)
            return (p.poll() is None)
        except OSError:
            return False
    webbrowser.BackgroundBrowser.open = patchedOpen

def _restart_miro(obj=None):
    root = resources.appRoot().encode('mbcs')
    args = [sys.executable, os.path.join(root, 'application.ini')]
    theme = config.get(prefs.THEME_NAME)
    if theme is not None:
        args += ['--theme', '"%s"' % theme]
    os.chdir(root)
    os.execv(sys.executable, args)


def _is_flash_installed():
    return os.path.exists(os.path.join(
            specialfolders.getSpecialFolder('System'),
            'Macromed', 'Flash', 'flashplayer.xpt'))


def _install_flash():
    def http_success(info):
        fd, filename = tempfile.mkstemp(suffix='.exe')
        output = os.fdopen(fd, 'wb')
        output.write(info['body'])
        output.close()
        code = subprocess.call([filename, '/S'])
        try:
            os.unlink(filename)
        except OSError, e:
            # not Access Denied
            if e.errno != 13:
                raise

        if code:
            # FAIL!
            print 'error installing flash'
            config.set(prefs.FLASH_REQUEST_COUNT, 0)
        else:
            try:
                webbrowser.open(FLASH_EULA_URL)
            except WindowsError, e:
                if e.errno not in (2, 22):
                    raise
                # Application not found
                # fake it by calling explorer
                os.system("explorer %s" % FLASH_EULA_URL)

            # FIXME
            title = _("Restart %(appname)s?", {"appname": config.get(prefs.SHORT_APP_NAME)})
            description = _(
                "To enable the Flash plugin, %(appname)s needs to be restarted.  "
                "Click Yes to shut %(appname)s down, or No to do it later.",
                {"miro": config.get(prefs.SHORT_APP_NAME)}
            )

            dialog = dialogs.ChoiceDialog(title, description,
                                          dialogs.BUTTON_YES,
                                          dialogs.BUTTON_NO)

            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_YES:
                    app.controller.shutdown()
                    shutdown._handlers[:1] = [(_restart_miro, (), {})]

            dialog.run(callback)

    def http_failure(error):
        print 'error downloading flash', error
        config.set(prefs.FLASH_REQUEST_COUNT, 0)

    httpclient.grabURL(FLASH_INSTALL_URL, http_success, http_failure)

def check_flash_install():
    request_count = config.get(prefs.FLASH_REQUEST_COUNT)
    if _is_flash_installed() or request_count > 0:
        return

    title = _("Install Flash?")
    description = _(
        "For the best %(appname)s experience, you should install Adobe Flash.  Do this now?",
        {"appname": config.get(prefs.SHORT_APP_NAME)}
    )

    dialog = dialogs.ThreeChoiceDialog(title, description,
                                       dialogs.BUTTON_YES,
                                       dialogs.BUTTON_NOT_NOW,
                                       dialogs.BUTTON_NO)

    def callback(dialog):
        if dialog.choice is None or dialog.choice == dialogs.BUTTON_NOT_NOW:
            return
        if dialog.choice == dialogs.BUTTON_YES:
            _install_flash()
        else:
            config.set(prefs.FLASH_REQUEST_COUNT, 1)

    dialog.run(callback)
