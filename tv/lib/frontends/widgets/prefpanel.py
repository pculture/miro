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
from miro.frontends.widgets import keyboard
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.plat import resources
from miro.plat.utils import filename_to_unicode, get_logical_cpu_count
from miro.plat.frontends.widgets.bonjour import install_bonjour
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.gtcache import gettext as _, gettext_lazy
from miro import gtcache

# Note: we do an additional import from prefpanelset half way down the file.


ERROR_IMAGE_PATH = resources.path('images/pref_panel_error.png')

def build_error_image():
    """Builds a hidden/hideable error image widget for controls that
    hold values that are naughty.

    :returns: hidden error image
    """
    image = widgetutil.HideableWidget(
        widgetutil.align_center(
            widgetutil.align_middle(
                widgetset.ImageDisplay(widgetset.Image(ERROR_IMAGE_PATH)),
                top_pad=6)))
    # reserve space for the image, since we don't want the text entry
    # to move when we show it (#16429)
    image.set_size_request(*image.child().get_size_request())
    image.hide()
    return image

def create_value_checker(min_=None, max_=None):
    """Returns a checker function that checks bounds."""
    def _integer_checker(error_widget, v):
        if (((min_ != None and v < min_) or
             (max_ != None and v > max_))):
            error_widget.show()
            return False
        else:
            error_widget.hide()
        return True
    return _integer_checker

def text_is_not_blank(error_widget, value):
    """
    Checks that the given text field is not blank.
    """
    if value != u'':
        error_widget.hide()
        return True
    else:
        error_widget.show()
        return False

def attach_boolean(widget, descriptor, sensitive_widget=None,
                   manualconfig=None):
    """This is for preferences implemented as a checkbox where the
    value is True or False.

    It allows for a sensitive_widget tuple which are disabled or enabled
    when this widget is checked or unchecked.

    widget - widget
    descriptor - prefs preference
    sensitive_widget - tuple of widgets that are sensitive to this boolean
        or None
    manualconfig - Callback to deal with configuration changes manually.
         Disables listening for changes witin the config system and auto
         enable and disable of dependent widgets.
    """
    def boolean_changed(widget):
        app.config.set(descriptor, widget.get_checked())
        if sensitive_widget != None:
            if widget.get_checked():
                [sw.enable() for sw in sensitive_widget]
            else:
                [sw.disable() for sw in sensitive_widget]

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            widget.freeze_signals()
            widget.set_checked(app.config.get(descriptor))
            if sensitive_widget != None:
                if widget.get_checked():
                    [sw.enable() for sw in sensitive_widget]
                else:
                    [sw.disable() for sw in sensitive_widget]
            widget.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)

    widget.set_checked(app.config.get(descriptor))
    if sensitive_widget != None:
        if widget.get_checked():
            [sw.enable() for sw in sensitive_widget]
        else:
            [sw.disable() for sw in sensitive_widget]

    callback = manualconfig if manualconfig else boolean_changed
    widget.connect('toggled', callback)

def attach_radio(widget_values, descriptor, manualconfig=None):
    def radio_changed(widget):
        for w, v in widget_values:
            if widget is w:
                app.config.set(descriptor, v)

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            pref_value = app.config.get(descriptor)
            for w, v in widget_values:
                if v == pref_value:
                    w.freeze_signals()
                    w.set_selected()
                    w.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)

    pref_value = app.config.get(descriptor)
    for w, v in widget_values:
        if v == pref_value:
            w.set_selected()
    callback = manualconfig if manualconfig else radio_changed
    for w, v in widget_values:
        w.connect('clicked', callback)

def attach_integer(widget, descriptor, error_widget, check_function=None,
                   manualconfig=None):
    """This is for preferences implemented as a text entry where the
    value is an integer.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    :param widget: widget
    :param descriptor: prefs preference
    :param error_widget: widget with show/hide methods that shows when
        the value is bad
    :param check_function: function with signature ``widget * int -> boolean``
        that checks the value for appropriateness
    :param manualconfig - Callback to deal with configuration changes manually.
         Disables listening for changes witin the config system and auto
         enable and disable of dependent widgets.
    """
    def check_value(widget):
        try:
            check_function(error_widget, int(widget.get_text().strip()))
        except ValueError:
            error_widget.show()

    def restore(widget, error_widget):
        widget.freeze_signals()
        widget.set_text(str(app.config.get(descriptor)))
        widget.thaw_signals()
        error_widget.hide()

    def save_value(widget):
        try:
            v = int(widget.get_text().strip())
            if ((check_function != None and
              not check_function(error_widget, v))):
                restore(widget, error_widget)
                return
            if manualconfig:
                manualconfig(widget)
            else:
                app.config.set(descriptor, v)
        except ValueError:
            restore(widget, error_widget)
            pass

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            widget.freeze_signals()
            widget.set_text(str(app.config.get(descriptor)))
            widget.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)
    widget.set_text(str(app.config.get(descriptor)))
    if check_function:
        widget.connect('changed', check_value)
    widget.connect('focus-out', save_value)

def float_value_to_text(value):
    """Converts a float value to a nice text string for a TextEntry.
    """
    # strip off trailing 0s and if there's a . at the end, strip that
    # off, too.
    text = "%.3f" % value
    while text.endswith("0"):
        text = text[:-1]
    if text.endswith("."):
        text = text[:-1]
    if not text:
        text = "0"
    return text

def attach_float(widget, descriptor, error_widget, check_function=None,
                 manualconfig=None):
    """This is for preferences implemented as a text entry where the
    value is a float.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    :param widget: widget
    :param descriptor: prefs preference
    :param error_widget: widget with show/hide methods that shows when
        the value is bad
    :param check_function: function with signature
        ``widget * float -> boolean`` that checks the value for
        itemappropriateness
    :param manualconfig - Callback to deal with configuration changes manually.
         Disables listening for changes witin the config system and auto
         enable and disable of dependent widgets.
    """
    def check_value(widget):
        try:
            check_function(error_widget, float(widget.get_text().strip()))
        except ValueError:
            error_widget.show()

    def restore(widget, error_widget):
        widget.freeze_signals()
        widget.set_text(float_value_to_text(app.config.get(descriptor)))
        widget.thaw_signals()
        error_widget.hide()

    def save_value(widget):
        try:
            v = float(widget.get_text().strip())
            if ((check_function != None and
              not check_function(error_widget, v))):
                restore(widget, error_widget)
                return
            if manualconfig:
                manualconfig(widget)
            else:
                app.config.set(descriptor, v)
        except ValueError:
            restore(widget, error_widget)
            pass

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            widget.freeze_signals()
            widget.set_text(float_value_to_text(app.config.get(descriptor)))
            widget.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)
    widget.set_text(float_value_to_text(app.config.get(descriptor)))
    if check_function:
        widget.connect('changed', check_value)
    widget.connect('focus-out', save_value)

def attach_text(widget, descriptor, error_widget=None, check_function=None,
                manualconfig=None):
    """This is for text entry preferences.

    It allows for a check_function which takes a widget and a value
    and returns True if the value is ok, False if not.

    :param widget: widget
    :param descriptor: prefs preference
    :param error_widget: widget with show/hide methods that shows when
        the value is bad
    :param check_function: function with signature ``widget * int -> boolean``
        that checks the value for appropriateness
    :param manualconfig - Callback to deal with configuration changes manually.
         Disables listening for changes witin the config system and auto
         enable and disable of dependent widgets.
    """
    def check_value(widget):
        try:
            check_function(error_widget,
                           widget.get_text().strip().encode('utf-8'))
        except ValueError:
            error_widget.show()

    def restore(widget, error_widget):
        widget.freeze_signals()
        widget.set_text(str(app.config.get(descriptor)))
        widget.thaw_signals()
        error_widget.hide()

    def save_value(widget):
        try:
            v = widget.get_text().strip().encode('utf-8')
            if check_function is not None:
                if not check_function(error_widget, v):
                    restore(widget, error_widget)
                    return
            if manualconfig:
                manualconfig(widget)
            else:
                app.config.set(descriptor, v)
        except ValueError:
            restore(widget, error_widget)
            pass

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            widget.freeze_signals()
            widget.set_text(str(app.config.get(descriptor)))
            widget.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)

    widget.set_text(app.config.get(descriptor))
    if check_function:
        widget.connect('changed', check_value)
    widget.connect('focus-out', save_value)

def attach_combo(widget, descriptor, values, manualconfig=None):
    """This is for preferences implemented as an option menu where there
    is a set of possible values of which only one can be chosen.

    widget - widget
    descriptor - prefs preference
    values - the list of all possible values as strings
    manualconfig - Callback to deal with configuration changes manually.
         Disables listening for changes witin the config system and auto
         enable and disable of dependent widgets.
    """
    def combo_changed(widget, index):
        app.config.set(descriptor, values[index])

    def on_config_changed(obj, key, value):
        if key == descriptor.key:
            value = app.config.get(descriptor)
            widget.freeze_signals()
            try:
                widget.set_selected(values.index(value))
            except ValueError:
                widget.set_selected(1)
            widget.thaw_signals()

    if not manualconfig:
        app.frontend_config_watcher.connect('changed', on_config_changed)

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

def add_panel(name, title, panel_builder_class,
              image_name='images/pref_tab_general.png'):
    """Adds a panel to the preferences panel list.

    :param name: a name for the panel--this is used internally
    :param title: the name of the panel; appears in tabs on the side and
        the top of the panel
    :param panel_builder: function ``None -> widget`` that builds the panel
        and returns it
    :param image_name: the image to use in the tabs; defaults to
        the general tab image
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
    def __init__(self):
        PanelBuilder.__init__(self)
        self.disable_net_lookup_buttons = False

    def build_widget(self):
        v = widgetset.VBox(8)
        self.pack_startup_shutdown_section(v)
        self.pack_sidebar_section(v)
        self.pack_language_section(v)
        self.pack_echonest_section(v)
        pack_extras(v, "general")
        return v

    def pack_startup_shutdown_section(self, v):
        startup_shutdown_heading = dialogwidgets.heading(
                                       _('Startup / Shutdown'))
        v.pack_start(startup_shutdown_heading)

        run_at_startup_cbx = widgetset.Checkbox(_(
            "Automatically run %(appname)s when I log in.",
            {'appname': app.config.get(prefs.SHORT_APP_NAME)}))
        attach_boolean(run_at_startup_cbx, prefs.RUN_AT_STARTUP)
        v.pack_start(run_at_startup_cbx)

        remember_last_display_cbx = widgetset.Checkbox(_(
            "When starting up %(appname)s, remember what screen I was on "
            "when I last quit.",
            {'appname': app.config.get(prefs.SHORT_APP_NAME)}))
        attach_boolean(remember_last_display_cbx, prefs.REMEMBER_LAST_DISPLAY)
        v.pack_start(remember_last_display_cbx)

        warn_if_downloading_cbx = widgetset.Checkbox(
            _("Warn me if I attempt to quit with downloads in progress."))
        attach_boolean(warn_if_downloading_cbx,
                       prefs.WARN_IF_DOWNLOADING_ON_QUIT)
        v.pack_start(warn_if_downloading_cbx)

        warn_if_converting_cbx = widgetset.Checkbox(
            _("Warn me if I attempt to quit with conversions in progress."))
        attach_boolean(warn_if_converting_cbx,
                       prefs.WARN_IF_CONVERTING_ON_QUIT)
        v.pack_start(warn_if_converting_cbx)

    def pack_sidebar_section(self, v):
        sidebar_heading = dialogwidgets.heading(_('Sidebar'))
        v.pack_start(sidebar_heading)

        cbx = widgetset.Checkbox(_('Show videos from podcasts in the Videos '
                                   'section.'))
        attach_boolean(cbx, prefs.SHOW_PODCASTS_IN_VIDEO)
        v.pack_start(cbx)

        cbx = widgetset.Checkbox(_('Show audio from podcasts in the Music '
                                   'section.'))
        attach_boolean(cbx, prefs.SHOW_PODCASTS_IN_MUSIC)
        v.pack_start(cbx)

    def pack_language_section(self, v):
        # FIXME - need to automatically generate list of available
        # languages in correct language
        lang_options = gtcache.get_languages()
        lang_options.insert(0, ("system", _("System default")))

        lang_option_menu = widgetset.OptionMenu([op[1] for op in lang_options])
        attach_combo(lang_option_menu, prefs.LANGUAGE,
                     [op[0] for op in lang_options])

        language_heading = dialogwidgets.heading(_("Language"))
        v.pack_start(language_heading)

        v.pack_start(widgetutil.align_left(
            dialogwidgets.note(
                    _("(Changing the language requires you to "
                      "restart %(appname)s.)",
                      {"appname": app.config.get(prefs.SHORT_APP_NAME)}))))

        v.pack_start(widgetutil.align_left(
            widgetutil.build_control_line((
                        widgetset.Label(_('Display in:')), lang_option_menu))))

    def pack_echonest_section(self, v):
        heading = dialogwidgets.heading(
            _("Music Album Art and Info Cleanup"))
        v.pack_start(heading)

        help_text = _('Online lookup can find matching album art and song '
                      'info for all your audio files')
        v.pack_start(widgetset.Label(help_text))

        # Link to the data providers for net lookup.  This method doesn't look
        # the best, but hopefully it can be translated somewhat decently.
        provider_links = widgetset.HBox()
        provider_links.pack_start(widgetset.Label(_("Via:")))
        provider_links.pack_start(widgetset.Label(" "))
        echonest_link = widgetutil.LinkButton(_('Echonest'))
        seven_digital_link = widgetutil.LinkButton(_('7Digital'))
        provider_links.pack_start(echonest_link)
        provider_links.pack_start(widgetset.Label(" "))
        provider_links.pack_start(seven_digital_link)
        def on_echonest_click(button):
            app.widgetapp.open_url("http://the.echonest.com/")
        echonest_link.connect("clicked", on_echonest_click)
        def on_7digital_click(button):
            app.widgetapp.open_url("http://www.7digital.com/")
        seven_digital_link.connect("clicked", on_7digital_click)
        v.pack_start(widgetutil.align_center(provider_links))

        self.run_net_lookup_button = widgetset.Button(
            _('Run Online Lookup for All Current Music'))
        self.run_net_lookup_button.connect(
            'clicked', self.net_lookup_button_clicked, True)
        self.remove_net_lookup_button = widgetset.Button(
            _("Remove All Lookup data"))
        self.remove_net_lookup_button.connect(
            'clicked', self.net_lookup_button_clicked, False)

        v.pack_start(widgetutil.build_control_line(
            (self.run_net_lookup_button, self.remove_net_lookup_button)))

        self.net_lookup_label = widgetset.Label(self._net_lookup_label_text())
        v.pack_start(self.net_lookup_label)

        cb_text = _('Automatically run online lookup for any new audio files '
                    'that I add to Miro.')
        cbx = widgetset.Checkbox(cb_text)
        attach_boolean(cbx, prefs.NET_LOOKUP_BY_DEFAULT)
        v.pack_start(cbx)
        self._update_net_lookup_butons()

    def net_lookup_button_clicked(self, button, value):
        messages.SetNetLookupEnabled(None, value).send_to_backend()
        self.disable_net_lookup_buttons = True
        self._update_net_lookup_butons()

    def enable_net_lookup_buttons(self):
        self.disable_net_lookup_buttons = False
        self._update_net_lookup_butons()

    def update_net_lookup_counts(self):
        self.net_lookup_label.set_text(self._net_lookup_label_text())
        self._update_net_lookup_butons()

    def _net_lookup_label_text(self):
        global _net_lookup_counts

        return _("Using lookup data for %(net_lookup_count)s "
                 "out of %(total_count)s items", {
                     'net_lookup_count': _net_lookup_counts[0],
                     'total_count': _net_lookup_counts[1],
                 })

    def _update_net_lookup_butons(self):
        """Enable/Disable the buttons for echonest lookup."""
        global _net_lookup_counts

        net_lookup_count, total_count = _net_lookup_counts

        if self.disable_net_lookup_buttons:
            self.run_net_lookup_button.disable()
            self.remove_net_lookup_button.disable()
        elif net_lookup_count == total_count:
            self.run_net_lookup_button.disable()
            self.remove_net_lookup_button.enable()
        elif net_lookup_count == 0:
            self.run_net_lookup_button.enable()
            self.remove_net_lookup_button.disable()
        else:
            self.run_net_lookup_button.enable()
            self.remove_net_lookup_button.enable()


class PodcastsPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()

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

        view_options = [
                (WidgetStateStore.STANDARD_VIEW, _("Standard view")),
                (WidgetStateStore.LIST_VIEW, _("List view")),
            ]
        view_option_menu = widgetset.OptionMenu([op[1] for op in view_options])
        attach_combo(view_option_menu, prefs.PODCASTS_DEFAULT_VIEW,
            [op[0] for op in view_options])

        grid.pack(dialogwidgets.heading(
                _("Default settings for new podcasts:")),
                grid.ALIGN_LEFT, span=2)
        grid.end_line(spacing=2)
        grid.pack(dialogwidgets.note(
                _("(These can be changed using the podcast's settings "
                  "button)")),
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

        grid.pack_label(_("Default view:"),
                dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(view_option_menu)
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
        max_manual_error = build_error_image()
        attach_integer(max_manual,
                       prefs.MAX_MANUAL_DOWNLOADS,
                       max_manual_error,
                       create_value_checker(min_=0))
        grid.pack(max_manual)
        grid.pack(max_manual_error, grid.ALIGN_LEFT)
        grid.end_line(spacing=6)

        grid.pack_label(_('Maximum number of auto-downloads at a time:'))
        max_auto = widgetset.TextEntry()
        max_auto.set_width(5)
        max_auto_error = build_error_image()
        attach_integer(max_auto, prefs.DOWNLOADS_TARGET,
                       max_auto_error,
                       create_value_checker(min_=0))
        grid.pack(max_auto)
        grid.pack(max_auto_error, dialogwidgets.ControlGrid.ALIGN_LEFT)
        grid.end_line(spacing=12)

        vbox.pack_start(grid.make_table())

        grid = dialogwidgets.ControlGrid()
        grid.pack(dialogwidgets.heading(_("Bittorrent:")),
                  grid.ALIGN_LEFT, span=3)
        grid.end_line(spacing=12)

        cbx = widgetset.Checkbox( _('Limit upstream bandwidth to:'))
                    #avoid internet slowdowns'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        attach_boolean(cbx, prefs.LIMIT_UPSTREAM, (limit,))
        max_kbs = sys.maxint / (2**10) # highest value accepted: sys.maxint
                                       # bits per second in kb/s
        limit_error = build_error_image()
        attach_integer(limit, prefs.UPSTREAM_LIMIT_IN_KBS,
                       limit_error,
                       create_value_checker(min_=0, max_=max_kbs))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_("KB/s"))
        grid.pack(limit_error)
        grid.end_line(spacing=6)

        cbx = widgetset.Checkbox(_('Limit downstream bandwidth to:'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        limit_error = build_error_image()
        attach_boolean(cbx, prefs.LIMIT_DOWNSTREAM_BT, (limit,))
        attach_integer(limit, prefs.DOWNSTREAM_BT_LIMIT_IN_KBS,
                       limit_error,
                       create_value_checker(min_=0, max_=max_kbs))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_("KB/s"))
        grid.pack(limit_error)
        grid.end_line(spacing=6)

        cbx = widgetset.Checkbox(_('Limit torrent connections to:'))
        limit = widgetset.TextEntry()
        limit.set_width(5)
        limit_error = build_error_image()
        attach_boolean(cbx, prefs.LIMIT_CONNECTIONS_BT, (limit,))
        attach_integer(limit, prefs.CONNECTION_LIMIT_BT_NUM,
                       limit_error,
                       create_value_checker(min_=0, max_=65536))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack(limit_error)
        grid.end_line(spacing=6)

        min_port = widgetset.TextEntry()
        min_port.set_width(5)
        min_port_error = build_error_image()
        max_port = widgetset.TextEntry()
        max_port.set_width(5)
        max_port_error = build_error_image()
        attach_integer(min_port, prefs.BT_MIN_PORT,
                       min_port_error,
                       create_value_checker(min_=0, max_=65535))
        attach_integer(max_port, prefs.BT_MAX_PORT,
                       max_port_error,
                       create_value_checker(min_=0, max_=65535))

        grid.pack_label(_("Starting port:"),
                        dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(min_port)
        grid.pack(min_port_error)
        grid.end_line(spacing=6)

        grid.pack_label(_("Ending port:"),
                        dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(max_port)
        grid.pack(max_port_error)
        grid.end_line(spacing=12)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        grid = dialogwidgets.ControlGrid()
        cbx = widgetset.Checkbox(_('Automatically forward ports.  (UPNP)'))
        attach_boolean(cbx, prefs.USE_UPNP)
        vbox.pack_start(cbx, padding=4)

        cbx = widgetset.Checkbox(_('Use DHT to find more peers'))
        attach_boolean(cbx, prefs.USE_DHT)
        vbox.pack_start(cbx, padding=4)

        cbx = widgetset.Checkbox(_('Ignore unencrypted connections.'))
        attach_boolean(cbx, prefs.BT_ENC_REQ)
        vbox.pack_start(cbx)

        cbx = widgetset.Checkbox(
            _('Stop torrent uploads when this ratio is reached:'))
        limit = widgetset.TextEntry()
        limit_error = build_error_image()
        attach_boolean(cbx, prefs.LIMIT_UPLOAD_RATIO, (limit,))
        attach_float(limit, prefs.UPLOAD_RATIO,
                     limit_error,
                     create_value_checker(min_=0.0))
        grid.pack(cbx)
        grid.pack(limit)
        grid.pack(limit_error)
        grid.end_line(spacing=6)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        cbx = widgetset.Checkbox(_('Download HD video from YouTube'))
        attach_boolean(cbx, prefs.HIGH_QUALITY_DOWNLOADS)
        vbox.pack_start(cbx, padding=4)

        return vbox

class _MovieDirectoryHelper(object):
    """Helper class that contains widgets used to handle the Movie
    directory prefs.
    """
    def __init__(self):
        self.label = widgetset.Label()
        self.button = widgetset.Button(_("Change"))
        self.button.set_size(widgetconst.SIZE_SMALL)
        self.button.connect('clicked', self._on_button_clicked)

    def _on_button_clicked(self, button):
        d = dialogs.ask_for_directory(
            _("Choose Movies Directory"),
            initial_directory=app.config.get(prefs.MOVIES_DIRECTORY),
            transient_for=_pref_window)
        if d is not None:
            try:
                if not os.path.exists(d):
                    os.makedirs(d)
                if not os.access(d, os.W_OK):
                    raise IOError    # Pretend we got an IOError.
            except (OSError, IOError):
                dialogs.show_message(
                    _("Directory not valid"),
                    _("Directory '%(dir)s' could not be created.  Please "
                      "choose a directory you have write access to.",
                      {"dir": d}),
                    dialogs.WARNING_MESSAGE)
                return
            logging.debug("Created directory.  It's valid.")
            self.path = d
            self.label.set_text(filename_to_unicode(d))

    def set_initial_path(self):
        self.path = self.initial_path = app.config.get(prefs.MOVIES_DIRECTORY)
        self.label.set_text(filename_to_unicode(self.path))

    def on_window_closed(self):
        if self.path != self.initial_path:
            title = _("Migrate existing movies?")
            description = _(
                "You've selected a new folder to download movies "
                "to.  Should %(appname)s migrate your existing downloads "
                "there?  (Currently downloading movies will not be moved "
                "until they finish.)",
                {'appname': app.config.get(prefs.SHORT_APP_NAME)})
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
        self._table.allow_multiple_select = False
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
        self._changed_signal = None

    def _on_visible_clicked(self, renderer, iter_):
        row = app.watched_folder_manager.model[iter_]
        app.watched_folder_manager.change_visible(row[0], not row[2])

    def connect_signals(self):
        if self._changed_signal is None:
            self._changed_signal = app.watched_folder_manager.connect(
                'changed', self._on_folders_changed)

    def disconnect_signals(self):
        if self._changed_signal is not None:
            app.watched_folder_manager.disconnect(self._changed_signal)
            self._changed_signal = None

    def _on_folders_changed(self, watched_folder_manager):
        self._table.model_changed()
        self.check_no_folders()

    def check_no_folders(self):
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
            self.check_no_folders()

    def _remove_clicked(self, button):
        iter_ = self._table.get_selected()
        if iter_ is not None:
            id_ = app.watched_folder_manager.model[iter_][0]
            app.watched_folder_manager.remove(id_)

class FoldersPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()
        self.movie_dir_helper = _MovieDirectoryHelper()
        self.watched_folder_helper = _WatchedFolderHelper()

        grid.pack_label(_('Store downloads in this folder:'), span=2)
        grid.end_line(spacing=0)
        grid.pack(self.movie_dir_helper.label, grid.ALIGN_LEFT, pad_left=12)
        grid.pack(self.movie_dir_helper.button)
        grid.end_line(spacing=18)
        grid.pack_label(
            _('Watch for new video and audio items in these folders '
              'and include them in library:'), span=2, width=500)
        grid.end_line()
        grid.pack(self.watched_folder_helper.folder_list, pad_right=12)
        grid.pack(self.watched_folder_helper.button_box)
        return grid.make_table()

    def on_window_open(self):
        self.watched_folder_helper.connect_signals()
        self.watched_folder_helper.check_no_folders()
        self.movie_dir_helper.set_initial_path()

    def on_window_closed(self):
        self.watched_folder_helper.disconnect_signals()
        self.movie_dir_helper.on_window_closed()

class DiskSpacePanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()

        cbx = widgetset.Checkbox(
            _('Keep at least this much free space on my drive:'))
        limit = widgetset.TextEntry()
        limit.set_width(6)
        limit_error = build_error_image()
        attach_boolean(cbx, prefs.PRESERVE_DISK_SPACE, (limit,))

        def set_library_filter(self, typ, filter):
            self.library[typ] = filter
        attach_float(limit, prefs.PRESERVE_X_GB_FREE,
                     limit_error,
                     create_value_checker(min_=0.0))

        grid.pack(cbx)
        grid.pack(limit)
        grid.pack_label(_('GB'))
        grid.pack(limit_error)
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

        grid.pack_label(_('By default, video and audio items expire after:'),
                        extra_space=dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(expire_menu,
                  extra_space=dialogwidgets.ControlGrid.ALIGN_LEFT)

        return grid.make_table()

class SharingPanel(PanelBuilder):
    def __del__(self):
        call_on_ui_thread(
            lambda: app.sharing_manager.unregister_interest(self))
        PanelBuilder.__del__(self)

    def build_widget(self):
        vbox = widgetset.VBox()
        grid = dialogwidgets.ControlGrid()

        sharing_cbx = widgetset.Checkbox(_('Share my media library.'))
        sharing_warnonquit_cbx = widgetset.Checkbox(
            _('Warn on quit when others are connected to my media library.'))
        share_txt = widgetset.TextEntry()

        share_audio_cbx = widgetset.Checkbox(_('Share my music library.'))
        share_video_cbx = widgetset.Checkbox(_('Share my video library.'))
        share_feed_cbx = widgetset.Checkbox(_('Share my downloaded podcasts.'))

        def manual_configuration(widget):
            checked = widget.get_checked()
            if not app.sharing_manager.sharing_set_enable(self, checked):
                widget.set_checked(not checked)

        attach_boolean(sharing_cbx, prefs.SHARE_MEDIA,
                       [share_audio_cbx, share_video_cbx, share_feed_cbx,
                        sharing_warnonquit_cbx, share_txt],
                       manualconfig=manual_configuration)
        attach_boolean(sharing_warnonquit_cbx, prefs.SHARE_WARN_ON_QUIT)
        attach_boolean(share_audio_cbx, prefs.SHARE_AUDIO)
        attach_boolean(share_video_cbx, prefs.SHARE_VIDEO)
        attach_boolean(share_feed_cbx, prefs.SHARE_FEED)
        share_error = build_error_image()
        attach_text(share_txt, prefs.SHARE_NAME,
                    share_error,
                    check_function=text_is_not_blank)

        # Do this after the attach so we can override the preference
        # values.
        if not app.sharing_manager.mdns_present:
            sharing_cbx.disable()
            share_txt.disable()
            sharing_warnonquit_cbx.disable()
            share_audio_cbx.disable()
            share_video_cbx.disable()
            share_feed_cbx.disable()

        widgets = [sharing_cbx, share_audio_cbx, share_video_cbx,
                   share_feed_cbx, sharing_warnonquit_cbx, share_txt]
        callbacks = (self.sharing_start_volatile, self.sharing_end_volatile)
        # Register interest with the enable/disable provider for sharing.
        app.sharing_manager.register_interest(self, callbacks, widgets)

        vbox.pack_start(widgetutil.align_left(sharing_cbx, bottom_pad=6))
        vbox.pack_start(widgetutil.align_left(sharing_warnonquit_cbx,
                                              bottom_pad=6))

        grid.pack_label(_("Share Name:"),
                        dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(share_txt)
        grid.pack(share_error, dialogwidgets.ControlGrid.ALIGN_LEFT)
        vbox.pack_start(widgetutil.align_left(grid.make_table(), bottom_pad=6))

        vbox.pack_start(widgetutil.align_left(share_video_cbx, bottom_pad=6))
        vbox.pack_start(widgetutil.align_left(share_audio_cbx, bottom_pad=6))
        vbox.pack_start(widgetutil.align_left(share_feed_cbx, bottom_pad=6))

        if not app.sharing_manager.mdns_present:
            text = _("Bonjour is required for sharing. "
                     "Click on 'Install Bonjour' to install.")
            label = widgetset.Label()
            label.set_text(text)
            vbox.pack_start(widgetutil.align_center(label, top_pad=30,
                                                    bottom_pad=6))
            button = widgetset.Button(_("Install Bonjour"))
            button.connect('clicked', self.install_bonjour_clicked)
            vbox.pack_start(widgetutil.align_center(button, bottom_pad=6))

        pack_extras(vbox, "sharing")

        return vbox

    def sharing_start_volatile(self, value, tag, widgets):
        main = widgets[0]
        if not tag is self:
            main.set_checked(value)
        for w in widgets:
            w.disable()

    def sharing_end_volatile(self, value, tag, widgets):
        main = widgets[0]
        for w in widgets:
            if value or (not value and w is main):
                w.enable()
 
    def install_bonjour_clicked(self, button):
        call_on_ui_thread(install_bonjour)

class PlaybackPanel(PanelBuilder):
    def build_widget(self):
        v = widgetset.VBox()

        miro_cbx = widgetset.Checkbox(
                    _('Play media in %(appname)s.',
                      {"appname": app.config.get(prefs.SHORT_APP_NAME)}))
        separate_cbx = widgetset.Checkbox(
            _('Always play videos in a separate window.'))

        subtitles_cbx = widgetset.Checkbox(
            _('Automatically enable movie subtitles when available.'))

        videos_heading = dialogwidgets.heading(_("Video Playback"))
        resume_videos_cbx = widgetset.Checkbox(
            _('Resume playback from where the video was last stopped.'))
        continue_videos_cbx = widgetset.Checkbox(
               _('Play continuously - when one item finishes, play the next item in the list.'))

        music_heading = dialogwidgets.heading(_("Music Playback"))
        resume_music_cbx = widgetset.Checkbox(
            _('Resume playback from where the song was last stopped.'))
        continue_music_cbx = widgetset.Checkbox(
               _('Play continuously - when one item finishes, play the next item in the list.'))

        podcasts_heading = dialogwidgets.heading(_("Podcast Playback"))
        resume_podcasts_cbx = widgetset.Checkbox(
            _('Resume playback from where the podcast was last stopped.'))
        continue_podcasts_cbx = widgetset.Checkbox(
               _('Play continuously - when one item finishes, play the next item in the list.'))

        attach_boolean(miro_cbx, prefs.PLAY_IN_MIRO,
                       (separate_cbx, videos_heading,
                        music_heading, podcasts_heading,
                        resume_videos_cbx,
                        continue_videos_cbx,
                        resume_music_cbx,
                        continue_music_cbx,
                        resume_podcasts_cbx,
                        continue_podcasts_cbx,
                        subtitles_cbx))

        v.pack_start(widgetutil.align_left(miro_cbx, bottom_pad=6))

        attach_boolean(separate_cbx, prefs.PLAY_DETACHED)
        v.pack_start(widgetutil.align_left(separate_cbx, bottom_pad=6))

        attach_boolean(subtitles_cbx, prefs.ENABLE_SUBTITLES)
        v.pack_start(widgetutil.align_left(subtitles_cbx, bottom_pad=6))

        v.pack_start(widgetutil.align_left(videos_heading,
                     left_pad=3, top_pad=12 , bottom_pad=6))
        attach_boolean(resume_videos_cbx, prefs.RESUME_VIDEOS_MODE)
        v.pack_start(widgetutil.align_left(resume_videos_cbx, bottom_pad=6))
        attach_boolean(continue_videos_cbx, prefs.CONTINUOUS_VIDEO_PLAYBACK_MODE)
        v.pack_start(widgetutil.align_left(continue_videos_cbx, bottom_pad=6))

        v.pack_start(widgetutil.align_left(music_heading,
                     left_pad=3, top_pad=12 , bottom_pad=6))
        attach_boolean(resume_music_cbx, prefs.RESUME_MUSIC_MODE)
        v.pack_start(widgetutil.align_left(resume_music_cbx, bottom_pad=6))
        attach_boolean(continue_music_cbx, prefs.CONTINUOUS_MUSIC_PLAYBACK_MODE)
        v.pack_start(widgetutil.align_left(continue_music_cbx, bottom_pad=6))

        v.pack_start(widgetutil.align_left(podcasts_heading,
                     left_pad=3, top_pad=12 , bottom_pad=6))
        attach_boolean(resume_podcasts_cbx, prefs.RESUME_PODCASTS_MODE)
        v.pack_start(widgetutil.align_left(resume_podcasts_cbx, bottom_pad=6))
        attach_boolean(continue_podcasts_cbx, prefs.CONTINUOUS_PODCAST_PLAYBACK_MODE)
        v.pack_start(widgetutil.align_left(continue_podcasts_cbx, bottom_pad=6))

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
        max_concurrent_menu = widgetset.OptionMenu(
            [op[1] for op in max_concurrent])
        attach_combo(max_concurrent_menu, prefs.MAX_CONCURRENT_CONVERSIONS,
            [op[0] for op in max_concurrent])

        if count == 1:
            max_concurrent_menu.disable()

        grid.pack(dialogwidgets.label_with_note(
            _("Allow this many concurrent conversions:"),
            _("(changing this will not apply to currently running "
              "conversions)")),
            dialogwidgets.ControlGrid.ALIGN_RIGHT)
        grid.pack(max_concurrent_menu)
        grid.end_line(spacing=4)
        vbox.pack_start(widgetutil.align_left(grid.make_table()))

        pack_extras(vbox, "conversions")

        return vbox

class StoreHelper(object):
    def __init__(self, height=120):
        self._table = widgetset.TableView(app.store_manager.model)
        store_cell_renderer = widgetset.CellRenderer()
        store_cell_renderer.set_text_size(widgetconst.SIZE_SMALL)
        store_column = widgetset.TableColumn(
            _('Store'), store_cell_renderer, value=1)
        store_column.set_min_width(400)
        checkbox_cell_renderer = widgetset.CheckboxCellRenderer()
        checkbox_cell_renderer.set_control_size(widgetconst.SIZE_SMALL)
        checkbox_cell_renderer.connect('clicked', self._on_visible_clicked)
        visible_column = widgetset.TableColumn(
            _('Visible'), checkbox_cell_renderer, value=2)
        visible_column.set_min_width(50)
        self._table.add_column(store_column)
        self._table.add_column(visible_column)
        self._table.set_fixed_height(True)
        self._table.allow_multiple_select = False
        self._table.set_alternate_row_backgrounds(True)
        scroller = widgetset.Scroller(False, True)
        scroller.set_has_borders(True)
        scroller.add(self._table)
        scroller.set_size_request(-1, height)
        self.store_list = widgetset.VBox()
        self.store_list.pack_start(scroller)
        self._changed_signal = None

    def connect_signals(self):
        if self._changed_signal is None:
            self._changed_signal = app.store_manager.connect(
                'changed', self._on_stores_changed)

    def disconnect_signals(self):
        if self._changed_signal is not None:
            app.store_manager.disconnect(self._changed_signal)
            self._changed_signal = None

    def _on_stores_changed(self, manager):
        self._table.model_changed()

    def _on_visible_clicked(self, renderer, iter_):
        row = app.store_manager.model[iter_]
        new_value = not row[2]
        self._table.model.update_value(iter_, 2, new_value)
        app.store_manager.change_visible(row[0], new_value)


class StoresPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()
        self.store_helper = StoreHelper()

        grid.pack_label(_('MP3 stores:'), span=2)
        grid.end_line(spacing=0)
        grid.pack(self.store_helper.store_list, pad_right=12)
        return grid.make_table()

    def on_window_open(self):
        self.store_helper.connect_signals()

    def on_window_closed(self):
        self.store_helper.disconnect_signals()

class _ExtensionsHelper(object):
    def __init__(self):
        self._loaded = False

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
        self._table.allow_multiple_select = False
        self._table.set_alternate_row_backgrounds(True)
        self._table.connect('row-clicked', self._show_details)

        scroller = widgetset.Scroller(False, True)
        scroller.set_has_borders(True)
        scroller.add(self._table)
        scroller.set_size_request(-1, 120)
        self.extensions_list = widgetset.VBox()
        self.extensions_list.pack_start(scroller)

        self.details = widgetset.MultilineTextEntry()
        self.details.set_editable(False)
        scroller = widgetset.Scroller(False, True)
        scroller.set_has_borders(True)
        scroller.add(self.details)
        scroller.set_size_request(-1, 150)
        self.extension_details = widgetset.VBox()
        self.extension_details.pack_start(scroller)

    def load(self):
        # we only need to load all the extensions once.  however, this
        # gets called every time the pref panel pops up.
        if self._loaded:
            return
        self._loaded = True
        for ext in app.extension_manager.extensions:
            iter_ = self._model.append(ext.loaded, ext.name)
            self._iter_map[ext.name] = iter_

    def _show_details(self, renderer, iter_):
        row = self._model[iter_]
        ext = app.extension_manager.get_extension_by_name(row[1])

        text = []
        text.append(_("Name:  %(extensionname)s",
                      {"extensionname": ext.name}))
        text.append(_("Version:  %(extensionversion)s",
                      {"extensionversion": ext.version}))
        text.append("")
        text.append(_("Description:"))
        text.append(ext.description)
        self.details.set_text("\n".join(text))

    def _on_enabled_clicked(self, renderer, iter_):
        # FIXME - if this fails, then we need to check/uncheck
        # appropriately and throw up a dialog.
        #
        # or maybe we should just throw up the crash dialog?
        row = self._model[iter_]
        ext = app.extension_manager.get_extension_by_name(row[1])
        if not row[0]:
            # enable extension
            try:
                app.extension_manager.import_extension(ext)
                app.extension_manager.load_extension(ext)
            except StandardError, ie:
                logging.exception("extension import or load error")
                msg = _("Extension %(extensionname)s failed to load: "
                        "%(errormessage)s",
                        {"extensionname": row[1],
                         "errormessage": str(ie)})
                dialogs.show_message(
                    _("Extension failed to load"), msg)
                return

            # only mark extension as enabled if there are no errors.
            app.extension_manager.enable_extension(ext)
        else:
            # always mark extension as disabled even if there are
            # errors.
            app.extension_manager.disable_extension(ext)
            try:
                app.extension_manager.unload_extension(ext)
            except StandardError, ie:
                logging.exception("extension unload error")
                msg = _("Extension %(extensionname)s failed to unload: "
                        "%(errormessage)s",
                        {"extensionname": row[1],
                         "errormessage": str(ie)})
                dialogs.show_message(
                    _("Extension failed to unload"), msg)
                return
        self.update_model()

    def update_model(self):
        for key, iter_ in self._iter_map.items():
            ext = app.extension_manager.get_extension_by_name(key)
            self._model.update_value(iter_, 0, ext.loaded)
        self._table.model_changed()

class ExtensionsPanel(PanelBuilder):
    def build_widget(self):
        grid = dialogwidgets.ControlGrid()
        self.extensions_helper = _ExtensionsHelper()

        grid.pack_label(
            _("Extensions are a beta feature.  Developers interested "
              "in writing extensions can learn more on our wiki."))
        grid.end_line(spacing=8)

        grid.pack_label(_("Extensions:"))
        grid.end_line(spacing=0)
        grid.pack(self.extensions_helper.extensions_list)
        grid.end_line(spacing=4)
        grid.pack_label(_("Details:"))
        grid.end_line(spacing=0)
        grid.pack(self.extensions_helper.extension_details)

        # FIXME - add preferences button here
        return grid.make_table()

    def on_window_open(self):
        self.extensions_helper.load()

# Add the initial panels
add_panel("general", gettext_lazy("General"), GeneralPanel,
          'images/pref_tab_general.png')
add_panel("feeds", gettext_lazy("Podcasts"), PodcastsPanel,
          'images/pref_tab_feeds.png')
add_panel("downloads", gettext_lazy("Downloads"), DownloadsPanel,
          'images/pref_tab_downloads.png')
add_panel("folders", gettext_lazy("Folders"), FoldersPanel,
          'images/pref_tab_folders.png')
add_panel("disk_space", gettext_lazy("Disk space"), DiskSpacePanel,
          'images/pref_tab_disk_space.png')
add_panel("playback", gettext_lazy("Playback"), PlaybackPanel,
          'images/pref_tab_playback.png')
add_panel("sharing", gettext_lazy("Sharing"), SharingPanel,
          'images/pref_tab_sharing.png')
add_panel("conversions", gettext_lazy("Conversions"), ConversionsPanel,
          'images/pref_tab_conversions.png')
add_panel("stores", gettext_lazy("Stores"), StoresPanel,
          'images/pref_tab_stores.png')
add_panel("extensions", gettext_lazy("Extensions"), ExtensionsPanel,
          'images/pref_tab_extensions.png')

class PreferencesWindow(widgetset.PreferencesWindow):
    def __init__(self):
        widgetset.PreferencesWindow.__init__(self, _("Preferences"))
        self.panel_builders = {}
        for name, title, image_name, panel_builder_class in _PANEL:
            panel_builder = panel_builder_class()
            self.panel_builders[name] = panel_builder
            panel = panel_builder.build_widget()
            alignment = widgetset.Alignment(xalign=0.5, yalign=0.5)
            alignment.set_padding(20, 20, 20, 20)
            alignment.add(panel)
            self.append_panel(name, alignment, title, image_name)

        self.finish_panels()

    def get_panel(self, name):
        return self.panel_builders[name]

    def select_panel(self, selection):
        if selection is None:
            widgetset.PreferencesWindow.select_panel(self, 0)
        else:
            for i, bits in enumerate(_PANEL):
                if bits[0] == selection:
                    widgetset.PreferencesWindow.select_panel(self, i)
                    break

    def do_key_press(self, key, mods):
        if key == keyboard.ESCAPE:
            self.close()
            return True
        return False

    def do_show(self):
        for panel_builder in self.panel_builders.values():
            panel_builder.on_window_open()

    def do_hide(self):
        for panel_builder in self.panel_builders.values():
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

def enable_net_lookup_buttons():
    global _pref_window
    if _pref_window is not None:
        _pref_window.get_panel('general').enable_net_lookup_buttons()

_net_lookup_counts = (0, 0)
def update_net_lookup_counts(net_lookup_count, total_count):
    global _pref_window
    global _net_lookup_counts

    _net_lookup_counts = (net_lookup_count, total_count)
    if _pref_window is not None:
        _pref_window.get_panel('general').update_net_lookup_counts()
