# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

from threading import Thread, Event
import util
import frontend
from gtcache import gettext as _
from gtcache import ngettext

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
        frontend.jsBridge.updateSearchProgress(_("(parsed %d files - found %d videos)") % (files, videos))
        return True

    # Alternate thread.
    def runSearch (self):
        self.files = util.gatherVideos(self.path, self.progressCallback)
        if not self.cancelled.isSet():
            count = len(self.files)
            frontend.jsBridge.searchFinished(ngettext("%d video found", "%d videos found", count) % (count,))

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
    frontend.jsBridge.searchCancelled("")

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
    frontend.jsBridge.performStartupTasks(os.path.expanduser("~"))
