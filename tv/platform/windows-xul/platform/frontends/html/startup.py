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

from threading import Thread, Event
import os
import _winreg

from miro import util
from miro import app
from miro import config
from miro import prefs
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.platform import resources

class _Search:
    def __init__(self, path):
        self.cancelled = Event()
        self.path = path
        self.last = None

    def run(self):
        thread = Thread(target=self.runSearch)
        thread.setDaemon(True)
        thread.start()

    def cancel(self):
        self.cancelled.set()

    # Alternate thread.
    def progressCallback(self, files, videos):
        if self.cancelled.isSet():
            return False
        app.jsBridge.updateSearchProgress(_("(parsed %d files - found %d videos)") % (files, videos))
        return True

    # Alternate thread.
    def runSearch (self):
        self.files = util.gatherVideos(self.path, self.progressCallback)
        if not self.cancelled.isSet():
            count = len(self.files)
            app.jsBridge.searchFinished(ngettext("%d video found", "%d videos found", count) % (count,))

    def getFiles (self):
        if self.cancelled.isSet():
            return None
        else:
            return self.files

search = None
callback = None

def doSearch(path):
    global search
    search = _Search(path)
    search.run()

def cancelSearch():
    search.cancel()
    app.jsBridge.searchCancelled("")

def finishStartup():
    if search:
        terminationCallback(search.getFiles())
    else:
        terminationCallback(None)
#    if widgetTree['radiobutton-startup-autostart-yes'].get_active():
#	 config_home = os.environ.get ('XDG_CONFIG_HOME',
#				       '~/.config')
#	 config_home = os.path.expanduser (config_home)
#	 autostart_dir = os.path.join (config_home, "autostart")
#	 destination = os.path.join (autostart_dir, "democracyplayer.desktop")
#	 try:
#	     os.makedirs(autostart_dir)
#	 except:
#	     pass
#	 try:
#	     shutil.copy (resource.sharePath('applications/democracyplayer.desktop'), autostart_dir)
#	 except:
#	     pass
#    try:
#	 dialog.destroy()
#    except:
#	 pass

def performStartupTasks(terminationCallback):
    global callback
    callback = terminationCallback
    app.jsBridge.performStartupTasks(os.path.expanduser("~"))

# This is windows specific right now. We don't need it on other platforms
def setRunAtStartup(value):
    runSubkey = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    try:
        folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, runSubkey, 0,
                _winreg.KEY_SET_VALUE)
    except WindowsError, e:
        if e.errno == 2: # registry key doesn't exist
            folder = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER,
                    runSubkey)
        else:
            raise
    if (value):
        # We don't use the app name for the .exe, so branded
        # versions work
        filename = os.path.join(resources.resourceRoot(),"..","Miro.exe")
        filename = os.path.normpath(filename)
        themeName = config.get(prefs.THEME_NAME)
        if themeName is not None:
            filename = "%s --theme \"%s\"" % (filename, themeName.replace("\\","\\\\").replace('"','\\"'))
        _winreg.SetValueEx(folder, config.get(prefs.LONG_APP_NAME), 0,_winreg.REG_SZ, filename)
    else:
        try:
            _winreg.DeleteValue(folder, config.get(prefs.LONG_APP_NAME))
        except WindowsError, e:
            if e.errno == 2: 
                # registry key doesn't exist, user must have deleted it
                # manual
                pass
            else:
                raise
