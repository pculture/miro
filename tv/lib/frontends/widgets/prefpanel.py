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

"""Defines the preferences panel and provides an API for adding new panels
and attaching items in the panel to preferences that are persisted between
Miro runs.

To build a new panel
====================

1. Define a function that takes no arguments and returns a widget.  This
   widget is a container that holds all the widgets that make up your panel.

2. Call ``add_panel`` with the name, title, and function to build the
   panel.  Title should be translated text.

When building a preference panel, it'll help to use the functions that begin
with ``attach_`` and ``create_``.

Refer to documentation for those functions for help.
"""

import logging
import sys
import os

from miro import app
from miro import messages
from miro import prefs
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import cellpack, widgetutil, window
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets.widgetutil import build_control_line
from miro.plat import resources
from miro.plat.utils import filename_to_unicode, get_logical_cpu_count
from miro.gtcache import gettext as _
from miro import gtcache

# Note: we do an additional import from prefpanelset half way down the file.

def create_integer_checker(min=None, max=None):
    """Returns a checker function that checks bounds."""
    def positive_integer_checker(widget, v):
        if min != None and v < min:
            widget.set_text(str(min))
        if max != None and v > max:
            widget.set_text(str(max))
        return True
    return positive_integer_checker

def create_float_checker(min=None, max=None):
    """Returns a checker function that checks bounds."""
    def positive_float_checker(widget, v):
        if min != None and v < min:
            widget.set_text(str(min))
        if max != None and v > min:
            widget.set_text(str(max))
        return True

def attach_boolean(widget, descriptor, sensitive_widget=None):
    """This is for preferences implemented as a checkbox where the
    value is True or False.

    It allows for a sensitive_widget tuple which are disabled or enabled
    when this widget is checked or unchecked.

    widget - widget
    descriptor - prefs preference
    sensitive_widget - tuple of widgets that are sensitive to this boolean
        or None
    """
    def boolean_changed(widget):
        app.config.set(descriptor, widget.get_checked())
        if sensitive_widget != None:
            if widget.get_checked():
                [sw.enable() for sw in sensitive_widget]
            else:
                [sw.disable() for sw in sensitive_widget]

    widget.set_checked(app.config.get(descriptor))
    if sensitive_widget != None:
        if widget.get_checked():
            [sw.enable() for sw in sensitive_widget]
        else:
            [sw.disable() for sw in sensitive_widget]

    widget.connect('toggled', boolean_changed)

def attach_radio(widget_values, descriptor):
    def radio_changed(widget):
        for w, v in widget_values:
            if widget is w:
                app.config.set(descriptor, v)

    pref_value = app.config.get(descriptor)
    for w, v in widget_values:
        w.connect('clicked', radio_changed)
        if v == pref_value:
            w.set_selected()

def attach_integer(widget, descriptor, check_function=None):
    """This is for preferences implemented as a text entry where the
    value is an integer.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    widget - widget
    descriptor - prefs preference
    check_function - function with signature ``widget * int -> boolean``
        that checks the value for appropriateness
    """
    def integer_changed(widget):
        try:
            v = int(widget.get_text().strip())
            if check_function != None:
                if not check_function(widget, v):
                    return
            app.config.set(descriptor, v)
        except ValueError, ve:
            pass

    widget.set_text(str(app.config.get(descriptor)))
    widget.connect('changed', integer_changed)

def attach_float(widget, descriptor, check_function=None):
    """This is for preferences implemented as a text entry where the
    value is a float.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    widget - widget
    descriptor - prefs preference
    check_function - function with signature ``widget * float -> boolean``
        that checks the value for appropriateness
    """
    def float_changed(widget):
        try:
            v = float(widget.get_text().strip())
            if check_function != None:
                if not check_function(widget, v):
                    return
            app.config.set(descriptor, v)
        except ValueError, ve:
            pass

    # strip off trailing 0s and if there's a . at the end, strip that
    # off, too.
    text = "%.3f" % app.config.get(descriptor)
    while text.endswith("0"):
        text = text[:-1]
    if text.endswith("."):
        text = text[:-1]
    if not text:
        text = "0"
    widget.set_text(text)
    widget.connect('changed', float_changed)

def attach_text(widget, descriptor, check_function=None):
    """This is for text entry preferences.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    widget - widget
    descriptor - prefs preference
    check_function - function with signature ``widget * int -> boolean``
        that checks the value for appropriateness
    """
    def text_changed(widget):
        v = widget.get_text().strip().encode('utf-8')
        if check_function != None:
            if not check_function(widget, v):
                return
        app.config.set(descriptor, v)

    widget.set_text(app.config.get(descriptor))
    widget.connect('changed', text_changed)

def attach_combo(widget, descriptor, values):
    """This is for preferences implemented as an option menu where there
    is a set of possible values of which only one can be chosen.

    widget - widget
    descriptor - prefs preference
    values - the list of all possible values as strings
    """
    def combo_changed(widget, index):
        app.config.set(descriptor, values[index])

    value = app.config.get(descriptor)
    try:
        widget.set_selected(values.index(value))
    except ValueError:
        widget.set_selected(1)
    widget.connect('changed', combo_changed)

def note_label(text):
    """Helper function for building a Note: xxx label.
    """
    note = widgetset.Label(text)
    note.set_wrap(True)
    note.set_size(widgetconst.SIZE_SMALL)
    return note

# Note: This has to be here so that the above functions have been defined
# before we try to import stuff from prefpanelset.  This prevents problems 
# resulting from the circular import.

from miro.plat.frontends.widgets import prefpanelset


class PanelBuilder(object):
    def build_widget(self):
        """Return a widget that should be used to display the panel."""
        raise NotImplementedError()

    def on_window_open(self):
        """Called when the preference window is opened.

        Can be overridden by subclasses.
        """
        pass

    def on_window_closed(self):
        """Called when the preference window is opened.

        Can be overridden by subclasses.
        """
        pass

# the panel list holding tuples of (name, image_name, panel_builder)
_PANEL = []

def add_panel(name, title, panel_builder_class, image_name='images/pref-tab-general.png'):
    """Adds a panel to the preferences panel list.

    name -- a name for the panel--this is used internally
    title -- the name of the panel; appears in tabs on the side and the top of
             the panel
    panel_builder -- function ``None -> widget`` that builds the panel
            and returns it
    image_name -- the image to use in the tabs; defaults to the general tab image
    """
    global _PANEL
    _PANEL.append( (name, title, image_name, panel_builder_class) )


# -----------------------
# Panel builder functions

def pack_extras(vbox, panel):
    extras = prefpanelset.get_platform_specific(panel)
    if extras:
        vbox.pack_start(widgetutil.pad(extras[0], top=12))
        [vbox.pack_start(mem) for mem in extras[1:]]

class GeneralPanel(PanelBuilder):
    def build_widget(self):
        v = widgetset.VBox(8)

        run_at_startup_cbx = widgetset.Checkbox(_(
            "Automatically run %(appname)s when I log in.",
            {'appname': app.config.get(prefs.SHORT_APP_NAME)}))
        attach_boolean(run_at_startup_cbx, prefs.RUN_AT_STARTUP)
        v.pack_start(run_at_startup_cbx)

        warn_if_downloading_cbx = widgetset.Checkbox(_("Warn me if I attempt to quit with downloads in progress."))
        attach_boolean(warn_if_downloading_cbx, prefs.WARN_IF_DOWNLOADING_ON_QUIT)
        v.pack_start(warn_if_downloading_cbx)

        warn_if_converting_cbx = widgetset.Checkbox(_("Warn me if I attempt to quit with conversions in progress."))
        attach_boolean(warn_if_converting_cbx, prefs.WARN_IF_CONVERTING_ON_QUIT)
        v.pack_start(warn_if_converting_cbx)

        # FIXME - need to automatically generate list of available languages
        # in correct language
        lang_options = gtcache.get_languages()
        lang_options.insert(0, ("system", _("System default")))

        lang_option_menu = widgetset.OptionMenu([op[1] for op in lang_options])
        attach_combo(lang_option_menu, prefs.LANGUAGE,
                     [op[0] for op in lang_options])
        v.pack_start(widgetutil.align_left(
            widgetutil.build_control_line((widgetset.Label(_("Language:")), lang_option_menu))))

        v.pack_start(widgetutil.align_left(
            dialogwidgets.note(_("(Changing the language requires you to restart Miro.)"))))
        
        pack_extras(v, "general")

        return v

class FeedsPanel(PanelBuilder):
    def build_widget(self):
        cc_options = [(1440, _("Every day")),
                      (60, _("Every hour")),
                      (30, _("Every 30 minutes")),
                      (-1 , _("Manually"))]
        cc_option_menu = widgetset.OptionMenu([op[1] for op in cc_options])
        attach_combo(cc_option_menu, prefs.CHECK_CHANNELS_EVERY_X_MN, 
            [op[0] for op in cc_options])

        ad_options = [("new", _("New")),
                      ("all", _("All")),
                      ("off", _("Off"))]
        ad_option_menu = widgetset.OptionMenu([op[1] for op in ad_options])

        attach_combo(ad_option_menu, prefs.CHANNEL_AUTO_DEFAULT, 
            [op[0] for op in ad_options])

        max_options = [(0, _("0")),
                       (20, _("20")),
                       (50, _("50")),
                       (100, _("100")),
                       (1000, _("1000"))]
        max_option_menu = widgetset.OptionMenu([op[1] for op in max_options])
        attach_combo(max_option_menu, prefs.MAX_OLD_ITEMS_DEFAULT, 
            [op[0] for op in max_options])

        grid = dialogwidgets.ControlGrid()
        grid.pack(dialogwidgets.heading(_("Default settings for new feeds:")), 
                grid.ALIGN_LEFT, span=2)
        grid.end_line(spacing=2)
        grid.pack(dialogwidgets.note(
                _("(These can be changed using the feed's settings button)")),
                grid.ALIGN_LEFT, span=2)
        grid.end_line(spacing=12)

        grid.pack_label(_("Check for new content:"),
                dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(cc_option_menu)
        grid.end_line(spacing=4)

        grid.pack_label(_("Auto-download setting:"),
                dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(ad_option_menu)
        grid.end_line(spacing=4)

        grid.pack(dialogwidgets.label_with_note(
            _("Remember this many old items:"),
            _("(in addition to the current contents)")),
            dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(max_option_menu)
        grid.end_line()

        return grid.make_table()

class DownloadsPanel(PanelBuilder):
    def build_widget(self):
        vbox = widgetset.VBox()

        grid = dialogwidgets.ControlGrid()

        grid.pack_label(_('Maximum number of manual downloads at a time:'))
        max_manual = widgetset.TextEntry()
        max_manual.set_width(5)
        attach_integer(max_manual, prefs.MAX_MANUAL_DOWNLOADS, create_integer_checker(min=0))
        grid.pack(max_manual)
        grid.end_line(spacing=6)

        grid.pack_label(_('Maximum number of auto-downloads at a time:'))
        max_auto = widgetset.TextEntry()
        max_auto.set_width(5)
        attach_integer(max_auto, prefs.DOWNLOADS_TARGET, create_integer_checker(min=0))
        grid.pack(max_auto)
        grid.end_line(spacing=12)
        
        vbox.pack_start(grid.make_table())

        grid = dialogwidgets.ControlGrid()
        grid.pack(dialogwidgets.heading(_("Bittorrent:")), grid.ALIGN_LEFT, span=3)
        grid.end_line(spacing=12)

        cbx = widgetset.Checkbox( _('Limit upstream bandwidth to:'))
                    #avoid internet slowdowns'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        attach_boolean(cbx, prefs.LIMIT_UPSTREAM, (limit,))
        max_kbs = sys.maxint / (2**10) # highest value accepted: sys.maxint
                                       # bits per second in kb/s
        attach_integer(limit, prefs.UPSTREAM_LIMIT_IN_KBS, create_integer_checker(min=0, max=max_kbs))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_("KB/s"))
        grid.end_line(spacing=6)

        cbx = widgetset.Checkbox(_('Limit downstream bandwidth to:'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        attach_boolean(cbx, prefs.LIMIT_DOWNSTREAM_BT, (limit,))
        attach_integer(limit, prefs.DOWNSTREAM_BT_LIMIT_IN_KBS, create_integer_checker(min=0, max=max_kbs))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_("KB/s"))
        grid.end_line(spacing=6)

        cbx = widgetset.Checkbox(_('Limit torrent connections to:'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        attach_boolean(cbx, prefs.LIMIT_CONNECTIONS_BT, (limit,))
        attach_integer(limit, prefs.CONNECTION_LIMIT_BT_NUM, create_integer_checker(min=0, max=65536))

        grid.pack(cbx)
        grid.pack(limit)
        grid.end_line(spacing=6)

        min_port = widgetset.TextEntry()
        min_port.set_width(5)
        max_port = widgetset.TextEntry()
        max_port.set_width(5)
        attach_integer(min_port, prefs.BT_MIN_PORT, create_integer_checker(min=0, max=65535))
        attach_integer(max_port, prefs.BT_MAX_PORT, create_integer_checker(min=0, max=65535))

        grid.pack_label(_("Starting port:"), dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(min_port)
        grid.end_line(spacing=6)

        grid.pack_label(_("Ending port:"), dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(max_port)
        grid.end_line(spacing=12)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        grid = dialogwidgets.ControlGrid()
        cbx = widgetset.Checkbox(_('Automatically forward ports.  (UPNP)'))
        attach_boolean(cbx, prefs.USE_UPNP)
        vbox.pack_start(cbx, padding=4)

        cbx = widgetset.Checkbox(_('Ignore unencrypted connections.'))
        attach_boolean(cbx, prefs.BT_ENC_REQ)
        vbox.pack_start(cbx)

        cbx = widgetset.Checkbox(_('Stop torrent uploads when this ratio is reached:'))
        limit = widgetset.TextEntry()
        attach_boolean(cbx, prefs.LIMIT_UPLOAD_RATIO, (limit,))
        attach_float(limit, prefs.UPLOAD_RATIO, create_float_checker(0.0, 1.0))
        grid.pack(cbx)
        grid.pack(limit)
        grid.end_line(spacing=6)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        return vbox

class _MovieDirectoryHelper(object):
    """Helper class that contains widgets used to handle the Movie directory
    prefs.
    """
    def __init__(self):
        self.label = widgetset.Label()
        self.button = widgetset.Button(_("Change"))
        self.button.set_size(widgetconst.SIZE_SMALL)
        self.button.connect('clicked', self._on_button_clicked)

    def _on_button_clicked(self, button):
        d = dialogs.ask_for_directory(_("Choose Movies Directory"),
                                      initial_directory=app.config.get(prefs.MOVIES_DIRECTORY),
                                      transient_for=_pref_window)
        if d is not None:
            try:
                if not os.path.exists(d):
                    os.makedirs(d)
                if not os.access(d, os.W_OK):
                    raise IOError    # Pretend we got an IOError.
            except (OSError, IOError):
                dialogs.show_message(_("Directory not valid"),
                                     _("Directory '%s' could not be created.  " +
                                       "Please choose a directory you have " +
                                       "write access to."),
                                     dialogs.WARNING_MESSAGE)
                return
            logging.info("Created directory.  It's valid.")
            self.path = d
            self.label.set_text(filename_to_unicode(d))

    def set_initial_path(self):
        self.path = self.initial_path = app.config.get(prefs.MOVIES_DIRECTORY)
        self.label.set_text(filename_to_unicode(self.path))

    def on_window_closed(self):
        if self.path != self.initial_path:
            title = _("Migrate existing movies?")
            description = _("You've selected a new folder to download movies "
                    "to.  Should %(appname)s migrate your existing downloads there? "
                    "(Currently downloading movies will not be moved until "
                    "they finish.)", {'appname': app.config.get(prefs.SHORT_APP_NAME)})
            response = dialogs.show_choice_dialog(title, description, 
                    (dialogs.BUTTON_MIGRATE, dialogs.BUTTON_DONT_MIGRATE),
                    transient_for=_pref_window)
            migrate = (response is dialogs.BUTTON_MIGRATE)
            m = messages.ChangeMoviesDirectory(self.path, migrate)
            m.send_to_backend()

class _WatchedFolderHelper(object):
    def __init__(self):
        self._table = widgetset.TableView(app.watched_folder_manager.model)
        folder_cell_renderer = widgetset.CellRenderer()
        folder_cell_renderer.set_text_size(widgetconst.SIZE_SMALL)
        folder_column = widgetset.TableColumn(
            _('folder'), folder_cell_renderer, value=1)
        folder_column.set_min_width(400)
        checkbox_cell_renderer = widgetset.CheckboxCellRenderer()
        checkbox_cell_renderer.set_control_size(widgetconst.SIZE_SMALL)
        checkbox_cell_renderer.connect('clicked', self._on_visible_clicked)
        visible_column = widgetset.TableColumn(
            _('visible'), checkbox_cell_renderer, value=2)
        visible_column.set_min_width(50)
        self._table.add_column(folder_column)
        self._table.add_column(visible_column)
        self._table.set_fixed_height(True)
        self._table.allow_multiple_select(False)
        self._table.set_alternate_row_backgrounds(True)
        self.add_button = widgetset.Button(_("Add"))
        self.add_button.set_size(widgetconst.SIZE_SMALL)
        self.add_button.connect('clicked', self._add_clicked)
        self.remove_button = widgetset.Button(_("Remove"))
        self.remove_button.set_size(widgetconst.SIZE_SMALL)
        self.remove_button.connect('clicked', self._remove_clicked)
        self.remove_button_holder = \
                widgetutil.HideableWidget(self.remove_button)
        self.button_box = widgetset.VBox()
        self.button_box.pack_start(self.add_button)
        self.button_box.pack_start(self.remove_button_holder)
        scroller = widgetset.Scroller(False, True)
        scroller.set_has_borders(True)
        scroller.add(self._table)
        scroller.set_size_request(-1, 120)
        self.folder_list = widgetset.VBox()
        self.folder_list.pack_start(scroller)
        self._check_no_folders()

    def _on_visible_clicked(self, renderer, iter):
        row = app.watched_folder_manager.model[iter]
        app.watched_folder_manager.change_visible(row[0], not row[2])

    def connect_signals(self):
        self._changed_signal = app.watched_folder_manager.connect('changed',
                self._on_folders_changed)

    def disconnect_signals(self):
        app.watched_folder_manager.disconnect(self._changed_signal)

    def _on_folders_changed(self, watched_folder_manager):
        self._table.model_changed()
        self._check_no_folders()

    def _check_no_folders(self):
        if len(app.watched_folder_manager.model) == 0:
            self.remove_button_holder.hide()
        else:
            self.remove_button_holder.show()

    def _add_clicked(self, button):
        dir = dialogs.ask_for_directory(_("Add Watched Folder"),
                initial_directory=app.config.get(prefs.MOVIES_DIRECTORY),
                transient_for=_pref_window)
        if dir is not None:
            app.watched_folder_manager.add(dir)
            self._check_no_folders()

    def _remove_clicked(self, button):
        iter = self._table.get_selected()
        if iter is not None:
            id = app.watched_folder_manager.model[iter][0]
            app.watched_folder_manager.remove(id)

class FoldersPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()
        self.movie_dir_helper = _MovieDirectoryHelper()
        self.watched_folder_helper = _WatchedFolderHelper()

        grid.pack_label(_('Store downloads in this folder:'), span=2)
        grid.end_line(spacing=0)
        movies_directory_label = widgetset.Label(
                app.config.get(prefs.MOVIES_DIRECTORY))
        grid.pack(self.movie_dir_helper.label, grid.ALIGN_LEFT, pad_left=12)
        grid.pack(self.movie_dir_helper.button)
        grid.end_line(spacing=18)
        grid.pack_label(_('Watch for new video and audio items in these folders '
                          'and include them in library:'), span=2)
        grid.end_line()
        grid.pack(self.watched_folder_helper.folder_list, pad_right=12)
        grid.pack(self.watched_folder_helper.button_box)
        return grid.make_table()

    def on_window_open(self):
        def query_lib(self, type):
            return self.library[type]
        self.watched_folder_helper.connect_signals()
        self.movie_dir_helper.set_initial_path()

    def on_window_closed(self):
        self.watched_folder_helper.disconnect_signals()
        self.movie_dir_helper.on_window_closed()

class DiskSpacePanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()

        cbx = widgetset.Checkbox(_('Keep at least this much free space on my drive:'))
        limit = widgetset.TextEntry()
        limit.set_width(6)
        note = widgetset.Label(_('GB'))
        attach_boolean(cbx, prefs.PRESERVE_DISK_SPACE, (limit,))

        def set_library_filter(self, typ, filter):
            self.library[typ] = filter
        attach_float(limit, prefs.PRESERVE_X_GB_FREE, create_float_checker(min=0.0))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_('GB'))
        grid.end_line(spacing=4)

        expire_ops = [(1, _('1 day')),
                (3, _('3 days')),
                (6, _('6 days')),
                (10, _('10 days')),
                (30, _('1 month')),
                (-1, _('never'))]
        expire_menu = widgetset.OptionMenu([op[1] for op in expire_ops])
        attach_combo(expire_menu, prefs.EXPIRE_AFTER_X_DAYS,
                [op[0] for op in expire_ops])

        grid.pack_label(_('By default, video and audio items expire after:'), extra_space=dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(expire_menu, extra_space=dialogwidgets.ControlGrid.ALIGN_LEFT)

        return grid.make_table()

class PlaybackPanel(PanelBuilder):
    def build_widget(self):
        v = widgetset.VBox()

        miro_cbx = widgetset.Checkbox(_('Play media in Miro.'))
        separate_cbx = widgetset.Checkbox(_('Always play videos in a separate window.'))
        resume_cbx = widgetset.Checkbox(_('Resume playing a video or audio item from the point it was last stopped.'))

        subtitles_cbx = widgetset.Checkbox(_('Automatically enable movie subtitles when available.'))

        rbg = widgetset.RadioButtonGroup()
        play_rb = widgetset.RadioButton(_("Play video and audio items one after another"), rbg)
        stop_rb = widgetset.RadioButton(_("Stop after each video or audio item"), rbg)

        attach_boolean(miro_cbx, prefs.PLAY_IN_MIRO, (separate_cbx, resume_cbx,
                                                      subtitles_cbx, play_rb,
                                                      stop_rb))
        v.pack_start(widgetutil.align_left(miro_cbx, bottom_pad=6))

        attach_boolean(separate_cbx, prefs.PLAY_DETACHED)
        v.pack_start(widgetutil.align_left(separate_cbx, bottom_pad=6))

        attach_boolean(resume_cbx, prefs.RESUME_VIDEOS_MODE)
        v.pack_start(widgetutil.align_left(resume_cbx, bottom_pad=6))

        attach_boolean(subtitles_cbx, prefs.ENABLE_SUBTITLES)
        v.pack_start(widgetutil.align_left(subtitles_cbx, bottom_pad=6))

        attach_radio([(stop_rb, True), (play_rb, False)], prefs.SINGLE_VIDEO_PLAYBACK_MODE)
        v.pack_start(widgetutil.align_left(play_rb), padding=2)
        v.pack_start(widgetutil.align_left(stop_rb))

        pack_extras(v, "playback")

        return v

class ConversionsPanel(PanelBuilder):
    def build_widget(self):
        vbox = widgetset.VBox()

        grid = dialogwidgets.ControlGrid()
        
        count = get_logical_cpu_count()
        max_concurrent = []
        for i in range(0, count):
            max_concurrent.append((i+1, str(i+1)))
        max_concurrent_menu = widgetset.OptionMenu([op[1] for op in max_concurrent])
        attach_combo(max_concurrent_menu, prefs.MAX_CONCURRENT_CONVERSIONS, 
            [op[0] for op in max_concurrent])

        if count == 1:
            max_concurrent_menu.disable()

        grid.pack(dialogwidgets.label_with_note(
            _("Allow this many concurrent conversions:"),
            _("(changing this will not apply to currently running conversions)")),
            dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(max_concurrent_menu)
        grid.end_line(spacing=4)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        pack_extras(vbox, "conversions")

        return vbox

class _ExtensionsHelper(object):
    def __init__(self):
        self._model = widgetset.TableModel('boolean', 'text')
        self._iter_map = {}

        self._table = widgetset.TableView(self._model)
        checkbox_cell_renderer = widgetset.CheckboxCellRenderer()
        checkbox_cell_renderer.set_control_size(widgetconst.SIZE_SMALL)
        checkbox_cell_renderer.connect('clicked', self._on_enabled_clicked)
        enabled_column = widgetset.TableColumn(
            _('enabled'), checkbox_cell_renderer, value=0)
        enabled_column.set_min_width(70)
        extension_cell_renderer = widgetset.CellRenderer()
        extension_cell_renderer.set_text_size(widgetconst.SIZE_SMALL)
        extension_column = widgetset.TableColumn(
            _('extension'), extension_cell_renderer, value=1)
        extension_column.set_min_width(400)
        self._table.add_column(enabled_column)
        self._table.add_column(extension_column)
        self._table.set_fixed_height(True)
        self._table.allow_multiple_select(False)
        self._table.set_alternate_row_backgrounds(True)
        self.details_button = widgetset.Button(_("Details"))
        self.details_button.set_size(widgetconst.SIZE_SMALL)
        self.details_button.connect('clicked', self._details_clicked)
        self.button_box = widgetset.VBox()
        self.button_box.pack_start(self.details_button)
        scroller = widgetset.Scroller(False, True)
        scroller.set_has_borders(True)
        scroller.add(self._table)
        scroller.set_size_request(-1, 120)
        self.extensions_list = widgetset.VBox()
        self.extensions_list.pack_start(scroller)

    def load(self):
        logging.info(">>> loading extensions table")
        for ext in app.extension_manager.extensions:
            logging.info(">>> adding extension %r", ext)
            iter_ = self._model.append(ext.loaded, ext.name)
            self._iter_map[ext.name] = iter_

    def unload(self):
        # wipe everything out
        for key in self._iter_map.keys():
            iter_ = self._iter_map.pop(key)
            self._model.remove(iter_)

    def _on_enabled_clicked(self, renderer, iter_):
        # FIXME - if this fails, then we need to check/uncheck
        # appropriately and throw up a dialog.
        #
        # or maybe we should just throw up the crash dialog?
        row = self._model[iter_]
        ext = app.extension_manager.get_extension_by_name(row[1])
        if not row[0]:
            app.extension_manager.enable_extension(ext)

            try:
                app.extension_manager.import_extension(ext)
            except ImportError, ie:
                logging.exception("import error")
                return

            try:
                app.extension_manager.load_extension(ext)
            except StandardError, ie:
                logging.exception("load error")
                return
        else:
            app.extension_manager.disable_extension(ext)
            try:
                app.extension_manager.unload_extension(ext)
            except StandardError, ie:
                logging.exception("unload error")
                return
        self.update_model()

    def update_model(self):
        for key, iter_ in self._iter_map.items():
            ext = app.extension_manager.get_extension_by_name(key)
            self._model.update_value(iter_, 0, ext.loaded)
        self._table.model_changed()

    def _details_clicked(self, button):
        ## iter = self._table.get_selected()
        ## if iter is not None:
        ##     id = app.watched_folder_manager.model[iter][0]
        ##     app.watched_folder_manager.remove(id)
        # FIXME
        logging.info("details clicked")
        pass

class ExtensionsPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()
        self.extensions_helper = _ExtensionsHelper()

        grid.pack(self.extensions_helper.extensions_list, pad_right=12)
        grid.pack(self.extensions_helper.button_box)
        return grid.make_table()

    def on_window_open(self):
        self.extensions_helper.load()

    def on_window_closed(self):
        self.extensions_helper.unload()

# Add the initial panels
add_panel("general", _("General"), GeneralPanel, 'images/pref-tab-general.png')
add_panel("feeds", _("Feeds"), FeedsPanel, 'images/pref-tab-feeds.png')
add_panel("downloads", _("Downloads"), DownloadsPanel, 'images/pref-tab-downloads.png')
add_panel("folders", _("Folders"), FoldersPanel, 'images/pref-tab-folders.png')
add_panel("disk_space", _("Disk space"), DiskSpacePanel, 'images/pref-tab-disk-space.png')
add_panel("playback", _("Playback"), PlaybackPanel, 'images/pref-tab-playback.png')
add_panel("conversions", _("Conversions"), ConversionsPanel, 'images/pref-tab-conversions.png')
add_panel("extensions", _("Extensions"), ExtensionsPanel, 'images/pref-tab-general.png')

class PreferencesWindow(widgetset.PreferencesWindow):
    def __init__(self):
        widgetset.PreferencesWindow.__init__(self, _("Preferences"))
        self.panel_builders = []
        for name, title, image_name, panel_builder_class in _PANEL:
            panel_builder = panel_builder_class()
            self.panel_builders.append(panel_builder)
            panel = panel_builder.build_widget()
            alignment = widgetset.Alignment(xalign=0.5, yalign=0.5)
            alignment.set_padding(20, 20, 20, 20)
            alignment.add(panel)
            self.append_panel(name, alignment, title, image_name)

        self.finish_panels()

    def select_panel(self, selection):
        if selection is None:
            widgetset.PreferencesWindow.select_panel(self, 0)
        else:
            for i, bits in enumerate(_PANEL):
                if bits[0] == selection:
                    widgetset.PreferencesWindow.select_panel(self, i)
                    break

    def do_show(self):
        for panel_builder in self.panel_builders:
            panel_builder.on_window_open()

    def do_hide(self):
        for panel_builder in self.panel_builders:
            panel_builder.on_window_closed()

_pref_window = None

def show_window(selection=None):
    """Displays the preferences window."""
    global _pref_window
    if _pref_window is None:
        _pref_window = PreferencesWindow()
    _pref_window.select_panel(selection)
    _pref_window.show()

def is_window_shown():
    return _pref_window and _pref_window.is_visible()

def hide_window():
    _pref_window.close()
