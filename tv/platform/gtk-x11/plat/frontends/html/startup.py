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

from miro.plat import resources
import MainFrame
import gtk_queue
import gtk
import os
import shutil
from threading import Thread
from miro import util
from miro import config
from miro import prefs
from miro.gtcache import gettext as _
from miro.gtcache import ngettext

class _Search:
    def __init__(self, widgetTree, path):
        self.cancelled = False
        self.widgetTree = widgetTree
        self.path = path

    def run(self):
        self.found = util.gatherVideos(self.path, self.progressCallback)

    def progressCallback(self, files, videos):
        while gtk.events_pending():
            gtk.main_iteration()
        if self.cancelled:
            return False
        label = _("(parsed %d files - found %d videos)") % (files, videos)
        self.widgetTree['label-startup-search-progress'].set_text(label)
        self.widgetTree['progressbar-startup-search'].pulse()
        return True

@gtk_queue.gtkAsyncMethod
def performStartupTasks(terminationCallback):
    widgetTree = MainFrame.WidgetTree(resources.path('miro.glade'), 'dialog-startup', 'miro')
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

            show_hide ('button-startup-forward', False)
            show_hide ('button-startup-search', searchSelected())
            show_hide ('button-startup-ok', not searchSelected())

            if status['inSearch']:
                widgetTree['button-startup-search'].set_sensitive(False)
                widgetTree['button-startup-ok'].set_sensitive(False)
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
    while (step < 2):
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
            terminationCallback(None)
            return
    terminationCallback(status['files'])
    config.set(prefs.RUN_DTV_AT_STARTUP, widgetTree['radiobutton-startup-autostart-yes'].get_active())
    updateAutostart()
    try:
        dialog.destroy()
    except:
        pass

def updateAutostart():
    if "KDE_FULL_SESSION" in os.environ:
        autostart_dir = "~/.kde/Autostart"
    else:
        config_home = os.environ.get ('XDG_CONFIG_HOME',
                                      '~/.config')
        autostart_dir = os.path.join (config_home, "autostart")
    autostart_dir = os.path.expanduser(autostart_dir)
    destination = os.path.join (autostart_dir, "miro.desktop")
    if config.get(prefs.RUN_DTV_AT_STARTUP):
        if os.path.exists(destination):
            return
        try:
            os.makedirs(autostart_dir)
        except:
            pass
        try:
            shutil.copy (resources.sharePath('applications/miro.desktop'), destination)
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
