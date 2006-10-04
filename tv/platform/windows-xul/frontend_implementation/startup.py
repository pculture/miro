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
	    print "Search Finished"
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
    print "Search Cancelled"
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
