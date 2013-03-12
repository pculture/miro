# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import logging
import os
import sys
import platform
import traceback
import webbrowser
from urlparse import urlparse
import _winreg
import time
import subprocess
import ctypes

import gobject
import gtk

from miro.gtcache import gettext as _
from miro import app
from miro import prefs
from miro.frontends.widgets import dialogs
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat import clipboard
from miro.plat import options
from miro.plat import resources
from miro.plat import associate
from miro.plat.renderers import gstreamerrenderer

from miro.plat.frontends.widgets import xulrunnerbrowser
from miro.frontends.widgets.gtk import gtkdirectorywatch
from miro.frontends.widgets.gtk import gtkmenus
from miro.frontends.widgets.gtk import trayicon
from miro.frontends.widgets.gtk import widgets
from miro.plat.frontends.widgets import bonjour
from miro.plat.frontends.widgets import embeddingwidget
from miro.plat.frontends.widgets import flash
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets.threads import call_on_ui_thread

BLACKLISTED_FILE_EXTENSIONS = ('.ade', '.adp', '.asx', '.bas', '.bat', '.chm',
                               '.cmd', '.com', '.cpl', '.crt', '.exe', '.hlp',
                               '.hta', '.inf', '.ins', '.isp', '.js', '.jse',
                               '.lnk', '.mda', '.mdb', '.mde', '.mdt', '.mdw',
                               '.mdz', '.msc', '.msi', '.msp', '.mst', '.ops',
                               '.pcd', '.pif', '.prf', '.reg', '.scf', '.scr',
                               '.sct', '.shb', '.shs', '.url', '.vb', '.vbe',
                               '.vbs', '.wsc', '.wsf', '.wsh')

def run_application():
    WindowsApplication().run()

class WindowsApplication(Application):
    def __init__(self):
        Application.__init__(self)
        self.showing_update_dialog = False

    def run(self):
        # wraps the real _run() with some code which sets the error mode
        # 0x8001 is SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX
        old_error_mode = ctypes.windll.kernel32.SetErrorMode(0x8001)
        try:
            self._run()
        finally:
            ctypes.windll.kernel32.SetErrorMode(0)

    def _run(self):

        self.initXULRunner()
        gobject.threads_init()
        embeddingwidget.init()
        self.menubar = gtkmenus.MainWindowMenuBar()
        self.startup()


        associate.associate_extensions(
            self._get_exe_location(), self._get_icon_location())

        winrel = platform.release()
        if winrel == "post2008Server":
            winrel += " (could be Windows 7)"
        logging.info("Windows version:   %s %s %s %s",
                     platform.system(),
                     winrel,
                     platform.machine(),
                     sys.getwindowsversion())
        logging.info("Python version:    %s", sys.version)
        logging.info("Gtk+ version:      %s", gtk.gtk_version)
        logging.info("PyGObject version: %s", gtk.ver)
        logging.info("PyGtk version:     %s", gtk.pygtk_version)
        try:
            import libtorrent
            logging.info("libtorrent:        %s", libtorrent.version)
        except AttributeError:
            logging.info("libtorrent:        unknown version")
        except ImportError:
            logging.exception("libtorrent won't load")
        try:
            import pycurl
            logging.info("pycurl:            %s", pycurl.version)
        except ImportError:
            logging.exception("pycurl won't load")

        renderers = gstreamerrenderer.make_renderers()
        app.audio_renderer, app.video_renderer = renderers
        app.get_item_type = gstreamerrenderer.get_item_type

        gtk.main()

        xulrunnerbrowser.shutdown()
        app.controller.on_shutdown()
        ctypes.cdll.winsparkle.win_sparkle_cleanup()

    def startup_ui(self):
        sys.excepthook = self.exception_handler
        Application.startup_ui(self)
        call_on_ui_thread(migrateappname.migrateVideos, 'Democracy', 'Miro')
        call_on_ui_thread(flash.check_flash_install)
        call_on_ui_thread(bonjour.check_bonjour_install)
        timer.add(15, self._init_autoupdate)
        
    def _init_autoupdate(self):
        if app.config.get(prefs.APP_FINAL_RELEASE) == u"0":
            # if this is not a final release, look at the beta
            # channel
            url = app.config.get(prefs.AUTOUPDATE_BETA_URL)
            logging.info("Using beta channel")
        else:
            # if this is a final release, look at the final
            # channel
            url = app.config.get(prefs.AUTOUPDATE_URL)
            logging.info("Using the final channel")
        ctypes.cdll.winsparkle.win_sparkle_set_appcast_url(
                                            url.encode('ascii', 'ignore'))
        ctypes.cdll.winsparkle.win_sparkle_set_app_details(
                                unicode(app.config.get(prefs.PUBLISHER)),
                                unicode(app.config.get(prefs.LONG_APP_NAME)),
                                unicode(app.config.get(prefs.APP_VERSION)))
        ctypes.cdll.winsparkle.win_sparkle_init()

    def on_config_changed(self, obj, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        if key == options.SHOW_TRAYICON.key:
            self.trayicon.set_visible(value)

        elif key == prefs.RUN_AT_STARTUP.key:
            self.set_run_at_startup(value)

    def _get_icon_location(self):
        # we set the icon first (if available) so that it doesn't flash
        # on when the window is realized in Application.build_window()
        icopath = os.path.join(resources.app_root(), "Miro.ico")
        if app.config.get(prefs.THEME_NAME) and app.config.get(options.WINDOWS_ICON):
            themeIcoPath = resources.theme_path(app.config.get(prefs.THEME_NAME),
                                                app.config.get(options.WINDOWS_ICON))
            if os.path.exists(themeIcoPath):
                icopath = themeIcoPath
        gtk.window_set_default_icon_from_file(icopath)
        return icopath

    def _get_exe_location(self):
            # We don't use the app name for the .exe, so branded
            # versions work
            filename = os.path.join(resources.root(), "..", "Miro.exe")
            filename = os.path.normpath(filename)
            themeName = app.config.get(prefs.THEME_NAME)
            if themeName is not None:
                themeName = themeName.replace("\\", "\\\\").replace('"', '\\"')
                filename = "%s --theme \"%s\"" % (filename, themeName)
            return filename

    def build_window(self):
        icopath = self._get_icon_location()
        Application.build_window(self)
        self.window.connect('save-dimensions', self.set_main_window_dimensions)
        self.window.connect('save-maximized', self.set_main_window_maximized)

        maximized = self.get_main_window_maximized()
        if maximized != None:
            if maximized:
                self.window._window.maximize()
            else:
                self.window._window.unmaximize()

        self.trayicon = trayicon.Trayicon(icopath)
        if app.config.get(options.SHOW_TRAYICON):
            self.trayicon.set_visible(True)
        else:
            self.trayicon.set_visible(False)

        if app.config.get(options.WINDOW_DIMENSIONS) == "":
            # Miro is being started for the first time on this computer
            # so we do some figuring to make sure the default width/height
            # fit on this monitor.
            geom = self.window.get_monitor_geometry()
            width = min(1024, geom.width)
            height = min(600, geom.height)
            self.window.set_frame(width=width, height=height)
        else:
            # check x, y to make sure the window is visible and fix it
            # if not
            self.window.check_position_and_fix()


    def on_close(self):
        if app.config.get(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE):
            ret = dialogs.show_choice_dialog(
                _("Close to tray?"),
                _("When you click the red close button, would you like %(appname)s to "
                  "close to the system tray or quit?  You can change this "
                  "setting later in the Options.",
                  {"appname": app.config.get(prefs.SHORT_APP_NAME)}),
                (dialogs.BUTTON_QUIT, dialogs.BUTTON_CLOSE_TO_TRAY))
            app.config.set(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE, False)
            if ret == dialogs.BUTTON_CLOSE_TO_TRAY:
                app.config.set(prefs.MINIMIZE_TO_TRAY, True)
            else:
                app.config.set(prefs.MINIMIZE_TO_TRAY, False)

        if app.config.get(prefs.MINIMIZE_TO_TRAY):
            self.trayicon.on_click(None)
        else:
            self.quit()

    def quit_ui(self):
        logging.debug('Destroying EmbeddingWidgets')
        embeddingwidget.shutdown()
        if hasattr(self, "trayicon"):
            logging.debug('Hiding tray icon')
            self.trayicon.set_visible(False)
        logging.debug('Running gtk.main_quit() ...')
        gtk.main_quit()

    def get_clipboard_text(self):
        return clipboard.get_text()

    def copy_text_to_clipboard(self, text):
        clipboard.set_text(text)

    def initXULRunner(self):
        app_dir = os.path.dirname(sys.executable)
        xul_dir = os.path.join(app_dir, 'xulrunner')
        xulrunnerbrowser.initialize(xul_dir, app_dir)
        xulrunnerbrowser.set_profile_dir(
            os.path.join(app.config.get(prefs.SUPPORT_DIRECTORY), 'profile'))
        xulrunnerbrowser.setup_user_agent(app.config.get(prefs.LONG_APP_NAME),
                app.config.get(prefs.APP_VERSION),
                app.config.get(prefs.PROJECT_URL))
        xulrunnerbrowser.install_window_creator(self)
        xulrunnerbrowser.add_cookie('dmusic_download_manager_enabled',
                                    '1.0.3',
                                    '.amazon.com',
                                    '/',
                                    time.time() + 3600 * 365 * 10) # 10 years

    def on_new_window(self, uri):
        self.open_url(uri)

    # This overwrites the Application.check_update method since the Windows
    # autoupdate code does not use autoupdate.py.
    def check_version(self):
        ctypes.cdll.winsparkle.win_sparkle_check_update_with_ui()

    def open_url(self, url):
        # It looks like the maximum URL length is about 2k. I can't
        # seem to find the exact value
        if len(url) > 2047:
            url = url[:2047]
        try:
            webbrowser.get("windows-default").open_new(url)
        except:
            logging.warn("Error opening URL: %r\n%s", url,
                    traceback.format_exc())
            recommendURL = app.config.get(prefs.RECOMMEND_URL)

            if url.startswith(app.config.get(prefs.VIDEOBOMB_URL)):
                title = _('Error Bombing Item')
            elif url.startswith(recommendURL):
                title = _('Error Recommending Item')
            else:
                title = _("Error Opening Website")

            scheme, host, path, params, query, fragment = urlparse(url)
            shortURL = '%s:%s%s' % (scheme, host, path)
            msg = _(
                "There was an error opening %(url)s.  Please try again in a few "
                "seconds",
                {"url": shortURL}
            )
            dialogs.show_message(title, msg, dialogs.WARNING_MESSAGE)

    def reveal_file(self, fn):
        if not os.path.isdir(fn):
            fn = os.path.dirname(fn)
        try:
            os.startfile(fn)
        except WindowsError, e:
            # bz:17264
            # Do we want to be more specific and return a message to user?
            pass

    def open_file(self, fn):
        _, extension = os.path.splitext(fn)
        extension = extension.lower()
        # FIXME:
        # This a way of reproducing the registry entry of Miro
        # by using the same string manipulation that is used in
        # setup.py to create CONFIG_PROG_ID which is then written
        # to the registry in the NSI installer.
        reg_value = app.config.get(prefs.LONG_APP_NAME)
        reg_value = reg_value.replace(" ", ".") + ".1"
        if self._is_associated_with(extension, reg_value):
            # The file we want to run externally is associated
            # with Miro. So open it with Windows Explorer instead.
            subprocess.Popen(r'explorer /select,"' + fn + r'"')
        elif extension in BLACKLISTED_FILE_EXTENSIONS:
            logging.warning("Extension " + str(extension) + " is blacklisted "
                            "and will not be executed")
        else:
            try:
                os.startfile(fn)
            except WindowsError, e:
                if e.winerror == 1155:
                    subprocess.Popen(r'explorer /select,"' + fn + r'"')

    # FIXME: this is very similar to the associate.is_associated() method.
    def _is_associated_with(self, extension, value=None):
        """ Checks whether an extension currently is
            associated with the given value, or,
            if none is given, whether the extension
            is associated with anything at all.
        """

        try:
            handle = _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT, extension,
                                     0, _winreg.KEY_QUERY_VALUE)
        except WindowsError, e:
            if e.errno == 2:
                # Key does not exist
                return False
            else:
                raise
        try:
            reg_value = _winreg.QueryValue(_winreg.HKEY_CLASSES_ROOT, extension)
            if value:
                is_associated = reg_value.lower() == value.lower()
            else:
                is_associated = len(reg_value) > 0
        except ValueError:
            is_associated = False
        return is_associated

    def get_main_window_dimensions(self):
        """Gets x, y, width, height from config.

        Returns Rect.
        """
        max_width = gtk.gdk.screen_width()
        max_height = gtk.gdk.screen_height()
        rect = app.config.get(options.WINDOW_DIMENSIONS)
        if rect == "":
            rect = "100,100,1024,600"
        rect = widgets.Rect.from_string(rect)
        rect.width = max(min(rect.width, max_width), 800)
        rect.height = max(min(rect.height, max_height - 20), 480)
        return rect

    def get_main_window_maximized(self):
        return app.config.get(options.WINDOW_MAXIMIZED)

    def set_main_window_dimensions(self, window, x, y, width, height):
        """Saves x, y, width, height to config.
        """
        app.config.set(options.WINDOW_DIMENSIONS, "%s,%s,%s,%s" % (x, y, width, height))

    def set_main_window_maximized(self, window, maximized):
        app.config.set(options.WINDOW_MAXIMIZED, maximized)

    def send_notification(self, title, body,
                          timeout=5000, attach_trayicon=True):
        print '--- %s ---' % title
        print body

    def set_run_at_startup(self, value):
        runSubkey = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        try:
            folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, runSubkey, 0,
                                     _winreg.KEY_SET_VALUE)
        except WindowsError, e:
            if e.errno == 2:
                # registry key doesn't exist
                folder = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER,
                                           runSubkey)
            else:
                raise

        if value:
            filename = self._get_exe_location()

            try:
                _winreg.SetValueEx(folder, app.config.get(prefs.LONG_APP_NAME), 0,
                                   _winreg.REG_SZ, filename)
            except WindowsError, e:
                # bz19936: permissions error when setting the registry key.  I
                # guess we can't do it.
                logging.warn("Error setting run at startup registry key: %s",
                             e)
                return

        else:
            try:
                _winreg.DeleteValue(folder, app.config.get(prefs.LONG_APP_NAME))
            except WindowsError, e:
                if e.errno == 2:
                    # registry key doesn't exist, user must have deleted it
                    # manual
                    pass
                else:
                    raise

    def handle_first_time(self, callback):
        Application.handle_first_time(self, callback)

    def handle_update_available(self, obj, item):
        # On Windows the autoupdate.py code is not used, so the
        # 'update-available' signal will never be emitted.
        pass
