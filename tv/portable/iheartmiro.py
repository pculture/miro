# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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
import sys
import tempfile
import glob

from miro import httpclient
from miro import config
from miro import prefs
from miro import dialogs
from miro.gtcache import gettext as _

def _firefox_executable():
    if sys.platform == "darwin":
        import AppKit
        return AppKit.NSWorkspace.sharedWorkspace().fullPathForApplication_("Firefox")
    else:
        search_path = ["/usr/bin/firefox", "C:\\Program Files\\Mozilla Firefox\\firefox.exe"]
        for poss in search_path:
            if os.path.isfile(poss):
                return poss
    return None

def _is_firefox_installed():
    return _firefox_executable() != None

def _is_browser_installed():
    return _is_firefox_installed() or _is_ie7_installed()

def _is_ie7_installed():
    if sys.platform != 'win32':
        return False
    import _winreg
    try:
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "Software\Microsoft\Internet Explorer")
    except EnvironmentError:
        return False
    version, type_ = _winreg.QueryValueEx(key, "Version")
    return (version[0] == u'7')

def _is_iheartmiro_installed():
    return _is_iheartmiro_installed_on_firefox() or _is_iheartmiro_installed_on_ie7()

def _is_iheartmiro_installed_on_firefox():
    id_ = "{216ec66d-214a-43ea-92f0-5373f8405c88}"
    locations = ["~/.mozilla/firefox/*/extensions/" + id_,
                 "~\\Application Data\\Mozilla\\Firefox\\Profiles\\*\\extensions\\" + id_,
                "~/Library/Application Support/Firefox/Profiles/*/extensions/" + id_ ]
    for location in locations:
        if glob.glob(os.path.expanduser(location)):
            return True
    return False

def _is_iheartmiro_installed_on_ie7():
    if sys.platform != 'win32':
        return False
    import _winreg
    id_ = "CLSID\{EB289F5D-2750-4BFC-91E1-4442686BCDC9}"
    try:
        _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT, id_)
    except EnvironmentError:
        return False
    return True

def _install_iheartmiro_firefox():
    def http_success(info):
        fd, filename = tempfile.mkstemp(suffix=".xpi", prefix="iHeartMiro-", text=False)
        output = os.fdopen(fd, "wb")
        output.write(info["body"])
        output.close()
        if sys.platform == "darwin":
            import AppKit
            AppKit.NSWorkspace.sharedWorkspace().openFile_withApplication_andDeactivate_(filename, "Firefox", True)
        else:
            exe = _firefox_executable()
            os.spawnl(os.P_NOWAIT, exe, exe, filename)

    def http_failure(error):
        print "error: %s" % error

    httpclient.grabURL("http://www.iheartmiro.org/iHeartMiro-latest.xpi", http_success, http_failure)

def _install_iheartmiro_ie7():
    def http_success(info):
        from miro.plat import specialfolders
        filename = os.path.join(specialfolders.appDataDirectory,
                                u'Participatory Culture Foundation',
                                'IHeartMiro.dll')
        output = open(filename, 'wb')
        output.write(info['body'])
        output.close()
        exe = "C:\\windows\\system32\\regsvr32.exe"
        os.spawnl(os.P_NOWAIT, exe, exe, '/s', filename)
        
    def http_failure(error):
        print "error: %s" % error

    httpclient.grabURL("http://www.iheartmiro.org/IHeartMiro.dll", http_success, http_failure)

def check_iheartmiro_install():
    # request_count makes it so that the second time you
    request_count = config.get(prefs.IHEARTMIRO_REQUEST_COUNT)

    # Comment out these two lines to do testing.
    if request_count >= 1:
        return

    if _is_iheartmiro_installed() or not _is_browser_installed():
        config.set(prefs.IHEARTMIRO_REQUEST_COUNT, 2)
        return

    if _is_firefox_installed():
        installer = 'Firefox'
        instructions = _("""If you click 'Install iHeartMiro' below, Firefox will launch and ask if it's ok.   Just say yes and you're done!   It takes about 7 seconds.  And thanks for your help.""")
    else:
        installer = 'Internet Explorer 7'
        instructions = _("""If you click 'Install iHeartMiro' below, we'll install the extension.  Thanks for your help.""")

    def callback(dialog):
        count = request_count
        if dialog.choice == dialogs.BUTTON_INSTALL_IHEARTMIRO:
            if installer == 'Firefox':
                _install_iheartmiro_firefox()
            else:
                _install_iheartmiro_ie7()

        if isinstance(dialog, dialogs.CheckboxDialog):
            if not dialog.checkbox_value:
                count = 2
            if dialog.checkbox_value:
                if count == 2:
                    count = 0
        else:
            count = count + 1
        config.set(prefs.IHEARTMIRO_REQUEST_COUNT, count)

    message = _(
        "An Effortless Way to Help Miro\n"
        "\n"
        "Miro is open-source and built by a non-profit.  We need your help to "
        "continue our work.\n"
        "\n"
        "I Heart Miro is a simple %(installer)s extension that gives a "
        "referral fee to the Miro organization when you shop at Amazon.  "
        "You'll never notice it, it doesn't cost you a thing, and it's easy "
        "to uninstall at any time.\n"
        "\n"
        "%(instructions)s"
    ) % { 'installer': installer, 'instructions': instructions }

    title = _("Install iHeartMiro?")
#    again = _ ("Ask me again later")
#    dialog = dialogs.CheckboxDialog(title, message, again, request_count < 1,
#                                    dialogs.BUTTON_INSTALL_IHEARTMIRO, dialogs.BUTTON_DONT_INSTALL)
    dialog = dialogs.ChoiceDialog(title, message, dialogs.BUTTON_INSTALL_IHEARTMIRO, dialogs.BUTTON_DONT_INSTALL)
    dialog.run(callback)
