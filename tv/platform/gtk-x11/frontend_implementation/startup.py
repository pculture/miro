import resources
import MainFrame
import gtk_queue
import gtk
import os
import shutil
from threading import Thread
import util
import config
import prefs
from gtcache import gettext as _
from gtcache import ngettext

class _Search:
    def __init__(self, widgetTree, path):
        self.cancelled = False
        self.widgetTree = widgetTree
        self.path = path

    def run(self):
        thread = Thread(target=self.runSearch)
        thread.setDaemon(True)
        thread.start()

        gtk.main()

    @gtk_queue.gtkSyncMethod
    def progressCallback(self, files, videos):
        if self.cancelled:
            return False
        label = _("(parsed %d files - found %d videos)") % (files, videos)
        self.widgetTree['label-startup-search-progress'].set_text(label)
        self.widgetTree['progressbar-startup-search'].pulse()
        return True

    @gtk_queue.gtkSyncMethod
    def finished(self, found):
        self.found = found
        gtk.main_quit()

    # Alternate thread.
    def runSearch (self):
        found = util.gatherVideos(self.path, self.progressCallback)
        self.finished(found)

def performStartupTasks(terminationCallback):
    widgetTree = MainFrame.WidgetTree(resources.path('democracy.glade'), 'dialog-startup', 'democracyplayer')
    dialog = widgetTree['dialog-startup']
    widgetTree['image-startup-tv'].set_from_file (resources.sharePath('pixmaps/miro-128x128.png'))
    dialog.set_icon_from_file (resources.sharePath('pixmaps/miro-128x128.png'))
    status = {}
    status['inSearch'] = False
    status['files'] = None
    status['searchSuccess'] = False
    def overall_cancel(*args):
        status['searchSuccess'] = False
        status['files'] = None
        count = 0
        widgetTree['label-startup-search-progress'].set_text (ngettext("%d video found", "%d videos found", count) % (count,))
        widgetTree['progressbar-startup-search'].set_fraction(0.0)
        updateUI()
    widgetTree['button-startup-search-cancel'].connect("clicked", overall_cancel)

    def searchSelected():
        return widgetTree['radiobutton-search-yes'].get_active() and not status['searchSuccess']            

    def updateUI(*args):
        widgetTree['notebook-startup'].set_current_page (step)

        def set_sensitive(toggle, widget):
            widgetTree[widget].set_sensitive(widgetTree[toggle].get_active())
        set_sensitive('radiobutton-search-yes', 'vbox-search-location')
        set_sensitive('radiobutton-search-custom', 'filechooserbutton-search-custom')

        def show_hide(widget, value):
            widgetTree[widget].set_sensitive(value)
            if value:
                widgetTree[widget].show()
            else:
                widgetTree[widget].hide()

        if step == 0:
            widgetTree['button-startup-back'].set_sensitive(False)

            show_hide ('button-startup-forward', True)
            show_hide ('button-startup-ok', False)
            show_hide ('button-startup-search', False)
        elif step == 1:
            widgetTree['button-startup-back'].set_sensitive(True)

            show_hide ('button-startup-forward', not searchSelected())
            show_hide ('button-startup-search', searchSelected())
            show_hide ('button-startup-ok', False)

            if status['inSearch']:
                widgetTree['button-startup-search'].set_sensitive(False)
                widgetTree['button-startup-forward'].set_sensitive(False)
                widgetTree['button-startup-back'].set_sensitive(False)

            if status['inSearch'] or status['searchSuccess']:
                widgetTree['vbox-startup-search'].set_sensitive(True)
                widgetTree['vbox-startup-search-controls'].set_sensitive(False)
            else:
                widgetTree['vbox-startup-search'].set_sensitive(False)
                widgetTree['vbox-startup-search-controls'].set_sensitive(True)
        elif step == 2:
            widgetTree['button-startup-back'].set_sensitive(True)

            show_hide ('button-startup-forward', False)
            show_hide ('button-startup-search', False)
            show_hide ('button-startup-ok', True)

    widgetTree ['radiobutton-search-yes'].connect("toggled", updateUI)
    widgetTree ['radiobutton-search-custom'].connect("toggled", updateUI)
 
    step = 0
    while (step < 3):
        # Setup step

        updateUI()

        response = dialog.run()
        if response == gtk.RESPONSE_NO:
            step = step - 1
        elif response == gtk.RESPONSE_YES:
            if step == 1:
                if searchSelected():
                    if widgetTree['radiobutton-search-custom'].get_active():
                        path = widgetTree['filechooserbutton-search-custom'].get_filename()
                    else:
                        path = os.path.expanduser('~')
                    widgetTree['vbox-startup-search'].show()

                    status['inSearch'] = True
                    updateUI()

                    search = _Search(widgetTree, path)

                    def cancel(*args):
                        search.cancelled = True
                    handler = widgetTree['button-startup-search-cancel'].connect("clicked", cancel)

                    search.run()

                    widgetTree['button-startup-search-cancel'].disconnect(handler)

                    status['inSearch'] = False
                    updateUI()

                    if not search.cancelled:
                        status['files'] = search.found
                        status['searchSuccess'] = True
                        try:
                            count = len(status['files'])
                        except:
                            count = 0
                        widgetTree['label-startup-search-progress'].set_text (ngettext("%d video found", "%d videos found", count) % (count,))
                        widgetTree['progressbar-startup-search'].set_fraction(1.0)
                    step = step - 1
            step = step + 1
            # Handle step
        else:
            status['files'] = None
            gtk_queue.queue.call_nowait(lambda : terminationCallback(None))
            return
    gtk_queue.queue.call_nowait(lambda : terminationCallback(status['files']))
    config.set(prefs.RUN_DTV_AT_STARTUP, widgetTree['radiobutton-startup-autostart-yes'].get_active())
    updateAutostart()
    try:
        dialog.destroy()
    except:
        pass

def updateAutostart():
    config_home = os.environ.get ('XDG_CONFIG_HOME',
                                  '~/.config')
    config_home = os.path.expanduser (config_home)
    autostart_dir = os.path.join (config_home, "autostart")
    destination = os.path.join (autostart_dir, "democracyplayer.desktop")
    if config.get(prefs.RUN_DTV_AT_STARTUP):
        if os.path.exists(destination):
            return
        try:
            os.makedirs(autostart_dir)
        except:
            pass
        try:
            shutil.copy (resources.sharePath('applications/democracyplayer.desktop'), destination)
        except:
            pass
    else:
        if not os.path.exists(destination):
            return
        try:
            os.remove (destination)
            os.removedirs(autostart_dir)
        except:
            pass
