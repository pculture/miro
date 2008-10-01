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

from miro import config, prefs
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import cellpack, imagepool, widgetutil, window
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets.widgetutil import build_control_line
from miro.plat import resources
from miro.dialogs import BUTTON_CLOSE
from miro.gtcache import gettext as _

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
        config.set(descriptor, widget.get_checked())
        if sensitive_widget != None:
            if widget.get_checked():
                [sw.enable_widget() for sw in sensitive_widget]
            else:
                [sw.disable_widget() for sw in sensitive_widget]

    widget.set_checked(config.get(descriptor))
    if sensitive_widget != None:
        if widget.get_checked():
            [sw.enable_widget() for sw in sensitive_widget]
        else:
            [sw.disable_widget() for sw in sensitive_widget]

    widget.connect('toggled', boolean_changed)

def attach_radio(widget_values, descriptor):
    def radio_changed(widget):
        for w, v in widget_values:
            if widget is w:
                config.set(descriptor, v)

    for w, v in widget_values:
        w.connect('clicked', radio_changed)
        if v == config.get(descriptor):
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
            config.set(descriptor, int(widget.get_text().strip()))
        except ValueError, ve:
            pass

    widget.set_text(str(config.get(descriptor)))
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
            config.set(descriptor, float(widget.get_text().strip()))
        except ValueError, ve:
            pass

    widget.set_text("%.3f" % config.get(descriptor))
    widget.connect('changed', float_changed)

def attach_combo(widget, descriptor, values):
    """This is for preferences implemented as an option menu where there
    is a set of possible values of which only one can be chosen.

    widget - widget
    descriptor - prefs preference
    values - the list of all possible values as strings
    """
    def combo_changed(widget, index):
        config.set(descriptor, values[index])

    value = config.get(descriptor)
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


# the panel list holding tuples of (name, image_name, panel_builder_function)
__PANEL = []

def add_panel(name, title, panel_builder_function, image_name='wimages/pref-tab-general.png'):
    """Adds a panel to the preferences panel list.

    name -- a name for the panel--this is used internally
    title -- the name of the panel; appears in tabs on the side and the top of
             the panel
    panel_builder_function -- function ``None -> widget`` that builds the panel
            and returns it
    image_name -- the image to use in the tabs; defaults to the general tab image
    """
    global __PANEL
    __PANEL.append( (name, title, image_name, panel_builder_function) )


# -----------------------
# Panel builder functions

def pack_extras(vbox, panel):
    extras = prefpanelset.get_platform_specific(panel)
    if extras:
        vbox.pack_start(widgetutil.pad(extras[0], top=12))
        [vbox.pack_start(mem) for mem in extras[1:]]

def _build_general_panel():
    """Build's the General tab and returns it."""
    v = widgetset.VBox()

    run_dtv_at_startup_cbx = widgetset.Checkbox(_("Automatically run Miro when I log in."))
    attach_boolean(run_dtv_at_startup_cbx, prefs.RUN_DTV_AT_STARTUP)
    v.pack_start(run_dtv_at_startup_cbx)

    warn_if_downloading_cbx = widgetset.Checkbox(_("Warn me if I attempt to quit with downloads in progress."))
    attach_boolean(warn_if_downloading_cbx, prefs.WARN_IF_DOWNLOADING_ON_QUIT)
    v.pack_start(warn_if_downloading_cbx)

    pack_extras(v, "general")

    return v

def _build_channels_panel():
    """Build's the Channels tab and returns it."""

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

    max_options = [(0, "0"),
                   (20, "20"),
                   (50, "50"),
                   (100, "100"),
                   (1000, "1000")]
    max_option_menu = widgetset.OptionMenu([op[1] for op in max_options])
    attach_combo(max_option_menu, prefs.MAX_OLD_ITEMS_DEFAULT, 
        [op[0] for op in max_options])

    grid = dialogwidgets.ControlGrid()
    grid.pack(dialogwidgets.heading(_("Default settings for new channels:")), 
            grid.ALIGN_LEFT, span=2)
    grid.end_line(spacing=0)
    grid.pack(dialogwidgets.note(
            _("(These can be changed using the channel's settings button)")),
            grid.ALIGN_LEFT, span=2)
    grid.end_line(spacing=12)

    grid.pack_label(_("Check for new content:"),
            dialogwidgets.ControlGrid.ALIGN_RIGHT)
    grid.pack(cc_option_menu)
    grid.end_line()

    grid.pack_label(_("Auto download setting:"),
            dialogwidgets.ControlGrid.ALIGN_RIGHT)
    grid.pack(ad_option_menu)
    grid.end_line()

    grid.pack(dialogwidgets.label_with_note(
        _("Remember this many old items:"),
        _("(in addition to the current contents)")),
        dialogwidgets.ControlGrid.ALIGN_RIGHT)
    grid.pack(max_option_menu)
    grid.end_line(spacing=0)

    return grid.make_table()

def _build_downloads_panel():
    vbox = widgetset.VBox()

    grid = dialogwidgets.ControlGrid()

    grid.pack_label(_('Maximum number of manual downloads at a time:'))
    max_manual = widgetset.TextEntry()
    max_manual.set_width(5)
    attach_integer(max_manual, prefs.MAX_MANUAL_DOWNLOADS, create_integer_checker(min=0))
    grid.pack(max_manual)
    grid.end_line()

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
    attach_integer(limit, prefs.UPSTREAM_LIMIT_IN_KBS, create_integer_checker(min=0))

    grid.pack(cbx)
    grid.pack(limit)
    grid.pack_label(_("KB/s"))
    grid.end_line()

    cbx = widgetset.Checkbox(_('Limit downstream bandwidth to:'))
    limit = widgetset.TextEntry()
    limit.set_width(5)
    attach_boolean(cbx, prefs.LIMIT_DOWNSTREAM_BT, (limit,))
    attach_integer(limit, prefs.DOWNSTREAM_BT_LIMIT_IN_KBS, create_integer_checker(min=0))

    grid.pack(cbx)
    grid.pack(limit)
    grid.pack_label(_("KB/s"))
    grid.end_line()

    cbx = widgetset.Checkbox(_('Limit torrent connections to:'))
    limit = widgetset.TextEntry()
    limit.set_width(5)
    attach_boolean(cbx, prefs.LIMIT_CONNECTIONS_BT, (limit,))
    attach_integer(limit, prefs.CONNECTION_LIMIT_BT_NUM, create_integer_checker(min=0))

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
    grid.end_line()

    grid.pack_label(_("Ending port:"), dialogwidgets.ControlGrid.ALIGN_RIGHT)
    grid.pack(max_port)
    grid.end_line(spacing=6)
    vbox.pack_start(widgetutil.align_left(grid.make_table()))

    grid = dialogwidgets.ControlGrid()
    cbx = widgetset.Checkbox(_('Automatically forward ports.  (UPNP)'))
    attach_boolean(cbx, prefs.USE_UPNP)
    vbox.pack_start(cbx)

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

def _build_folders_panel():
    v = widgetset.VBox()

    # FIXME - finish implementing this pane

    note = widgetset.Label(_('Store downloads in this folder:'))
    v.pack_start(widgetutil.align_left(note))
    v.pack_start(widgetset.Label("FIXME - implement this."))

    note = widgetset.Label(_(
        'Watch for new videos in these folders and include them in library:'
        ))
    v.pack_start(widgetutil.align_left(note))
    v.pack_start(widgetset.Label("FIXME - implement this."))

    return v

def _build_disk_space_panel():
    grid = dialogwidgets.ControlGrid()

    cbx = widgetset.Checkbox(_('Keep at least this much free space on my drive:'))
    limit = widgetset.TextEntry()
    limit.set_width(6)
    note = widgetset.Label(_('GB'))
    attach_boolean(cbx, prefs.PRESERVE_DISK_SPACE, (limit,))
    attach_float(limit, prefs.PRESERVE_X_GB_FREE, create_float_checker(min=0.0))

    grid.pack(cbx)
    grid.pack(limit)
    grid.pack_label(_('GB'))
    grid.end_line()

    expire_ops = [(1, _('1 day')),
            (3, _('3 days')),
            (6, _('6 days')),
            (10, _('10 days')),
            (30, _('1 month')),
            (-1, _('never'))]
    expire_menu = widgetset.OptionMenu([op[1] for op in expire_ops])
    attach_combo(expire_menu, prefs.EXPIRE_AFTER_X_DAYS,
            [op[0] for op in expire_ops])

    grid.pack_label(_('By default, videos expire after:'))
    grid.pack(expire_menu)

    return grid.make_table()

def _build_playback_panel():
    v = widgetset.VBox()

    cbx = widgetset.Checkbox(_('Resume playing a video from the point it was last stopped.'))
    attach_boolean(cbx, prefs.RESUME_VIDEOS_MODE)
    v.pack_start(widgetutil.align_left(cbx, bottom_pad=6))

    rbg = widgetset.RadioButtonGroup()
    play_rb = widgetset.RadioButton("Play videos one after another", rbg)
    stop_rb = widgetset.RadioButton("Stop after each video", rbg)
    attach_radio( [(stop_rb, True), (play_rb, False)], prefs.SINGLE_VIDEO_PLAYBACK_MODE)
    v.pack_start(widgetutil.align_left(play_rb))
    v.pack_start(widgetutil.align_left(stop_rb))

    pack_extras(v, "playback")

    return v


# Add the initial panels
add_panel("general", _("General"), _build_general_panel, 'wimages/pref-tab-general.png')
add_panel("channels", _("Channels"), _build_channels_panel, 'wimages/pref-tab-channels.png')
add_panel("downloads", _("Downloads"), _build_downloads_panel, 'wimages/pref-tab-downloads.png')
add_panel("folders", _("Folders"), _build_folders_panel, 'wimages/pref-tab-folders.png')
add_panel("disk_space", _("Disk space"), _build_disk_space_panel, 'wimages/pref-tab-disk-space.png')
add_panel("playback", _("Playback"), _build_playback_panel, 'wimages/pref-tab-playback.png')

def run_dialog(tab=None):
    """Displays the preferences dialog."""
    pref_window = widgetset.Dialog(_("Preferences"))
    try:
        try:
            tab_container = widgetset.TabContainer()

            for name, title, image_name, panel_builder in __PANEL:
                panel = panel_builder()
                alignment = widgetset.Alignment(xalign=0.5, yalign=0.0)
                alignment.set_padding(10, 20, 20, 20)
                alignment.add(panel)
                image = imagepool.get(resources.path(image_name))
                tab_container.append_tab(alignment, title, image)

            if tab == None:
                tab_container.select_tab(0)
            else:
                for i, bits in enumerate(__PANEL):
                    if bits[0] == tab:
                        tab_container.select_tab(i)
                        break
                else:
                    tab_container.select_tab(0)

            pref_window.set_extra_widget(tab_container)
            pref_window.add_button(BUTTON_CLOSE.text)
            pref_window.run()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("preferencespanel threw exception.")
    finally:
        pref_window.destroy()
