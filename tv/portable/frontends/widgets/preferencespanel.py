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

"""Defines the preferences panel."""

import logging

from miro import config, prefs
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import cellpack, imagepool, widgetutil, window
from miro.plat import resources
from miro.plat.frontends.widgets.widgetset import Rect
from miro.dialogs import BUTTON_CLOSE
from miro.gtcache import gettext as _

# FIXME - comment this module and add notes about how to use it externally.

def _hbox(*items):
    h = widgetset.HBox()
    [h.pack_start(item, padding=5) for item in items]
    return h

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

    widget.set_text(str(config.get(descriptor)))
    widget.connect('changed', float_changed)

def attach_combo(widget, descriptor, values):
    def combo_changed(widget, index):
        config.set(descriptor, values[index])

    value = config.get(descriptor)
    try:
        widget.set_selected(values.index(value))
    except ValueError:
        widget.set_selected(1)
    widget.connect('changed', combo_changed)

def build_general_panel():
    """Build's the General tab and returns it."""
    v = widgetset.VBox()

    run_dtv_at_startup_cbx = widgetset.Checkbox(_("Automatically run Miro when I log in."))
    v.pack_start(run_dtv_at_startup_cbx)

    warn_if_downloading_cbx = widgetset.Checkbox(_("Warn me if I attempt to quit with downloads in progress."))
    v.pack_start(warn_if_downloading_cbx)

    attach_boolean(run_dtv_at_startup_cbx, prefs.RUN_DTV_AT_STARTUP)
    attach_boolean(warn_if_downloading_cbx, prefs.WARN_IF_DOWNLOADING_ON_QUIT)

    return v

def build_channels_panel():
    """Build's the Channels tab and returns it."""
    v = widgetset.VBox()

    note = widgetset.Label(_("Check channels for new content"))
    cc_options = [(1440, _("Every day")),
                  (60, _("Every hour")),
                  (30, _("Every 30 minutes")),
                  (-1 , _("Manually"))]
    cc_option_menu = widgetset.OptionMenu([op[1] for op in cc_options])

    attach_combo(cc_option_menu, prefs.CHECK_CHANNELS_EVERY_X_MN, 
        [op[0] for op in cc_options])
    v.pack_start(_hbox(note, cc_option_menu))

    note = widgetset.Label(_("Note: You can set the frequency channels are checked for each channel in the channel's settings pane."))
    v.pack_start(note)

    ad_label = widgetset.Label(_("Auto download default settings for new channels:"))
    ad_options = [("new", _("New")),
                  ("auto", _("Auto")),
                  ("off", _("Off"))]
    ad_option_menu = widgetset.OptionMenu([op[1] for op in ad_options])

    attach_combo(ad_option_menu, prefs.CHANNEL_AUTO_DEFAULT, 
        [op[0] for op in ad_options])
    v.pack_start(_hbox(ad_label, ad_option_menu))

    note = widgetset.Label(_("By default, remember "))
    max_options = [(0, "0"),
                   (20, "20"),
                   (50, "50"),
                   (100, "100"),
                   (1000, "1000")]
    max_option_menu = widgetset.OptionMenu([op[1] for op in max_options])
    note2 = widgetset.Label(_("old items in addition to the current contents."))

    attach_combo(max_option_menu, prefs.MAX_OLD_ITEMS_DEFAULT, 
        [op[0] for op in max_options])
    v.pack_start(_hbox(note, max_option_menu, note2))

    return v

def build_downloads_panel():
    v = widgetset.VBox()

    note = widgetset.Label(_('Maximum number of manual downloads at a time:'))
    max_manual = widgetset.TextEntry()
    max_manual.set_width(5)
    attach_integer(max_manual, prefs.MAX_MANUAL_DOWNLOADS, create_integer_checker(min=0))
    v.pack_start(_hbox(note, max_manual))

    note = widgetset.Label(_('Maximum number of auto-downloads at a time:'))
    max_auto = widgetset.TextEntry()
    max_auto.set_width(5)
    attach_integer(max_auto, prefs.DOWNLOADS_TARGET, create_integer_checker(min=0))
    v.pack_start(_hbox(note, max_auto))

    note = widgetset.Label(_('Bittorrent:'))
    note.set_bold(True)
    v.pack_start(widgetutil.align_left(note))

    cbx = widgetset.Checkbox(_('To avoid internet slowdowns, limit upstream to:'))
    limit = widgetset.TextEntry()
    limit.set_width(5)
    note = widgetset.Label(_('KB/s'))
    attach_boolean(cbx, prefs.LIMIT_UPSTREAM, (limit,))
    attach_integer(limit, prefs.UPSTREAM_LIMIT_IN_KBS, create_integer_checker(min=0))
    v.pack_start(_hbox(cbx, limit, note))

    cbx = widgetset.Checkbox(_('Limit torrent downstream to:'))
    limit = widgetset.TextEntry()
    limit.set_width(5)
    note = widgetset.Label(_('KB/s'))
    attach_boolean(cbx, prefs.LIMIT_DOWNSTREAM_BT, (limit,))
    attach_integer(limit, prefs.DOWNSTREAM_BT_LIMIT_IN_KBS, create_integer_checker(min=0))
    v.pack_start(_hbox(cbx, limit, note))

    note = widgetset.Label(_('Use ports:'))
    min_port = widgetset.TextEntry()
    min_port.set_width(5)
    max_port = widgetset.TextEntry()
    max_port.set_width(5)
    attach_integer(min_port, prefs.BT_MIN_PORT, create_integer_checker(min=0, max=65535))
    attach_integer(max_port, prefs.BT_MAX_PORT, create_integer_checker(min=0, max=65535))
    v.pack_start(_hbox(note, min_port, widgetset.Label("-"), max_port))

    cbx = widgetset.Checkbox(_('Automatically forward ports.  (UPNP)'))
    attach_boolean(cbx, prefs.USE_UPNP)
    v.pack_start(cbx)

    cbx = widgetset.Checkbox(_('Ignore unencrypted connections.'))
    attach_boolean(cbx, prefs.BT_ENC_REQ)
    v.pack_start(cbx)

    cbx = widgetset.Checkbox(_('Stop torrent uploads when this ratio is reached:'))
    limit = widgetset.TextEntry()
    attach_boolean(cbx, prefs.LIMIT_UPLOAD_RATIO, (limit,))
    attach_float(limit, prefs.UPLOAD_RATIO, create_float_checker(0.0, 1.0))
    v.pack_start(_hbox(cbx, limit))

    return v

def build_folders_panel():
    v = widgetset.VBox()

    # FIXME - finish implementing this pane

    note = widgetset.Label(_('Store downloads in this folder:'))
    v.pack_start(widgetutil.align_left(note))
    v.pack_start(widgetset.Label("FIXME - implement this."))

    note = widgetset.Label(_('Watch for new videos in these folders and include them in library:'))
    v.pack_start(widgetutil.align_left(note))
    v.pack_start(widgetset.Label("FIXME - implement this."))

    return v

def build_disk_space_panel():
    v = widgetset.VBox()

    cbx = widgetset.Checkbox(_('Keep at least this much free space on my drive:'))
    limit = widgetset.TextEntry()
    limit.set_width(5)
    note = widgetset.Label(_('GB'))
    attach_boolean(cbx, prefs.PRESERVE_DISK_SPACE, (limit,))
    attach_float(limit, prefs.PRESERVE_X_GB_FREE, create_float_checker(min=0.0))

    v.pack_start(_hbox(cbx, limit, note))

    note = widgetset.Label(_('By default, videos expire after'))
    expire_ops = [(1, _('1 day')),
                  (3, _('3 days')),
                  (6, _('6 days')),
                  (10, _('10 days')),
                  (30, _('1 month')),
                  (-1, _('never'))]
    expire_menu = widgetset.OptionMenu([op[1] for op in expire_ops])
    attach_combo(expire_menu, prefs.EXPIRE_AFTER_X_DAYS,
        [op[0] for op in expire_ops])
    v.pack_start(_hbox(note, expire_menu))    

    return v

def build_playback_panel():
    v = widgetset.VBox()

    cbx = widgetset.Checkbox(_('Resume playing a video from the point it was last stopped.'))
    attach_boolean(cbx, prefs.RESUME_VIDEOS_MODE)
    v.pack_start(_hbox(cbx))

    rbg = widgetset.RadioButtonGroup()
    play_rb = widgetset.RadioButton("Play videos one after another", rbg)
    stop_rb = widgetset.RadioButton("Stop after each video", rbg)
    attach_radio( [(play_rb, True), (stop_rb, False)], prefs.SINGLE_VIDEO_PLAYBACK_MODE)
    v.pack_start(_hbox(play_rb))
    v.pack_start(_hbox(stop_rb))

    return v

def create_panel(title_text, panel_contents):
    title = widgetset.Label(title_text)
    title.set_bold(True)
    title.set_size(1.2)

    v = widgetset.VBox()
    v.pack_start(widgetutil.align_left(title))
    v.pack_start(panel_contents)

    return v

class TabRenderer(widgetset.CustomCellRenderer):
    def get_size(self, style, layout):
        return self.pack_tab(layout).get_size()

    def pack_tab(self, layout):
        #layout.set_font(0.77)
        titlebox = layout.textbox(self.tab_title)

        hbox = cellpack.HBox(spacing=4)
        hbox.pack(cellpack.align_middle(self.icon))
        hbox.pack(cellpack.align_middle(titlebox))
        return hbox

    def render(self, context, layout, selected, hotspot):
        layout.set_text_color(context.style.text_color)
        self.pack_tab(layout).render_layout(context)

class PreferenceTabList(widgetset.TableView):
    def __init__(self, widget_holder):
        # The model stores the title, image, and right-side widget for each
        # tab
        self.widget_holder = widget_holder
        model = widgetset.TableModel('text', 'object', 'object')
        widgetset.TableView.__init__(self, model)
        self.set_show_headers(False)
        self.add_column('tab', TabRenderer(), 150, tab_title=0, icon=1)

    def do_selection_changed(self):
        widget = self.model[self.get_selected()][2]
        self.widget_holder.set(widget)

PANEL = [
    (_("General"), 'wimages/pref-tab-general.png', build_general_panel),
    (_("Channels"), 'wimages/pref-tab-channels.png', build_channels_panel),
    (_("Downloads"), 'wimages/pref-tab-downloads.png', build_downloads_panel),
    (_("Folders"), 'wimages/pref-tab-folders.png', build_folders_panel),
    (_("Disk space"), 'wimages/pref-tab-disk-space.png', build_disk_space_panel),
    (_("Playback"), 'wimages/pref-tab-playback.png', build_playback_panel)
]

def add_panel(name, image_name, panel_builder_function):
    global PANEL
    PANEL.append( (name, image_name, panel_builder_function) )

def run_dialog():
    """Displays the preferences dialog."""
    pref_window = widgetset.Dialog(_("Preferences"))
    try:
        try:
            v = widgetset.VBox()
            main_area_holder = window.WidgetHolder()
            
            splitter = widgetset.Splitter()

            tab_list = PreferenceTabList(main_area_holder)

            max_height = max_width = 0
            for title, image_name, panel_builder in PANEL:
                panel = create_panel(title, panel_builder())
                image = imagepool.get_surface(resources.path(image_name))
                tab_list.model.append(title, image, panel)

                w, h = panel.get_size_request()
                max_width = max(max_width, w)
                max_height = max(max_height, h)

            main_area_holder.set_size_request(max_width, max_height)

            splitter.set_left(tab_list)
            splitter.set_left_width(200)
            tab_list.select(tab_list.model.first_iter())

            splitter.set_right(main_area_holder)

            v.pack_start(splitter)

            pref_window.set_extra_widget(v)
            pref_window.add_button(BUTTON_CLOSE.text)
            pref_window.run()
        except:
            logging.exception("preferencespanel threw exception.")
    finally:
        pref_window.destroy()
