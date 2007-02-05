import pygtk
pygtk.require("2.0")
import gtk
from gettext import gettext as _

trayicon_is_supported = False

# first check to see whether the version of GTK+ natively supports
# trayicons (the GtkStatusIcon widget).  Specifically we are looking
# for GTK+ version 2.10 or newer.  If we have it, we use our native
# python implementation.
if gtk.check_version(2,10,0) == None:        
    trayicon_is_supported = True
    class Trayicon(gtk.StatusIcon):
        def __init__(self, icon, main_frame):
            gtk.StatusIcon.__init__(self)
            self.main_frame = main_frame
            self.set_from_file(icon)
            self.set_visible(False)
            self.connect("activate", self.onClick)
            self.connect("popup-menu", self.on_popup_menu)
        def make_popup_menu_items(self):
            cb_handler = self.main_frame.callbackHandler
            menu_items = []
            menu_items.append((_("Settings"), cb_handler.on_preference))
            window = self.main_frame.widgetTree['main-window']
            if window.get_property('visible') == True:
                menu_items.append((_("Hide"), self.onClick))
            else:
                menu_items.append((_("Show"), self.onClick))
            menu_items.append((_("Quit"), cb_handler.on_quit_activate))
            return menu_items

        def on_popup_menu(self, status_icon, button, activate_time):
            popup_menu = gtk.Menu()
            for label, callback in self.make_popup_menu_items():
                item = gtk.MenuItem(label)
                item.connect('activate', callback)
                popup_menu.append(item)
            popup_menu.show_all()
            popup_menu.popup(None, None, gtk.status_icon_position_menu,
                    button, activate_time, status_icon)

        def onClick(self, widget):
            window = self.main_frame.widgetTree['main-window']
            if window.get_property('visible') == True:
                window.hide()
            else:
                window.show()

        def displayNotification(self, text):
            try:
                import pynotify
            except ImportError:
                return
            n = pynotify.Notification()
            n.set_property("status-icon", self)
            n.show()

# if we don't have GTK+ 2.10, then try to import our custom module,
# based on the older libegg code.
else:
    try:
        import _trayicon
        class Trayicon(_trayicon.Trayicon):
            pass
        trayicon_is_supported = True
    except ImportError:
        pass
