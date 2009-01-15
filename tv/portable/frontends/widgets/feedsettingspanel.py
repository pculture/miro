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

"""Defines the feed settings panel."""

import logging

from miro import app
from miro import config, prefs, messages
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import dialogwidgets
from miro.dialogs import BUTTON_DONE
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.frontends.widgets import separator
from miro.frontends.widgets import style
from miro.frontends.widgets.dialogs import MainDialog
from miro.frontends.widgets.widgetutil import build_control_line
from miro.util import clampText, returnsUnicode

@returnsUnicode
def get_formatted_default_expiration():
    """Returns the 'system' expiration delay as a formatted string
    """
    expiration = float(config.get(prefs.EXPIRE_AFTER_X_DAYS))
    formatted_expiration = u''
    if expiration < 0:
        formatted_expiration = _('never')
    elif expiration < 1.0:
        hours = int(expiration * 24.0)
        formatted_expiration = ngettext("%(count)d hour ago",
                                        "%(count)d hours ago",
                                        hours,
                                        {"count": hours})
    elif expiration >= 1 and expiration < 30:
        days = int(expiration)
        formatted_expiration = ngettext("%(count)d day ago",
                                        "%(count)d days ago",
                                        days,
                                        {"count": days})
    elif expiration >= 30:
        months = int(expiration / 30)
        formatted_expiration = ngettext("%(count)d month ago",
                                        "%(count)d months ago",
                                        months,
                                        {"count": months})
    return formatted_expiration

def _build_header(channel):
    v = widgetset.VBox(6)
    
    lab = widgetset.Label(clampText(channel.name, 60))
    lab.set_bold(True)
    lab.set_size(1.2)
    v.pack_start(widgetutil.align_left(lab))

    lab = widgetset.Label(clampText(channel.url, 80))
    lab.set_size(widgetconst.SIZE_SMALL)
    lab.set_color(widgetconst.DIALOG_NOTE_COLOR)
    v.pack_start(widgetutil.align_left(lab))

    return v

def _build_video_expires(channel, grid):
    grid.pack_label(_("Auto-Expire Videos:"), grid.ALIGN_RIGHT)

    expire_options = [
        ("system", _("Watched %(expiration)s (Default)",
                     {"expiration": get_formatted_default_expiration()})),
        ("24", _("Watched 1 day ago")),
        ("72", _("Watched 3 days ago")),
        ("144", _("Watched 6 days ago")),
        ("240", _("Watched 10 days ago")),
        ("720", _("Watched 1 month ago")),
        ("never", _("never"))
    ]
    expire_values = [e[0] for e in expire_options]
    expire_combo = widgetset.OptionMenu([e[1] for e in expire_options])

    if channel.expire == "system":
        selected = expire_values.index("system")
    elif channel.expire == "never":
        selected = expire_values.index("never")
    else:
        try:
            selected = expire_values.index(str(channel.expire_time))
        except ValueError:
            selected = 0
    expire_combo.set_selected(selected)

    def expire_changed(widget, index):
        value = expire_options[index][0]

        if value == "system":
            expire_type = "system"
            expire_time = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        elif value == "never":
            expire_type = "never"
            expire_time = 0
        else:
            expire_type = "feed"
            expire_time = int(value)

        messages.SetFeedExpire(channel, expire_type, expire_time).send_to_backend()
    expire_combo.connect('changed', expire_changed)

    grid.pack(expire_combo, grid.ALIGN_LEFT)

def _build_remember_items(channel, grid):
    grid.pack_label(_("Outdated Feed Items:"), grid.ALIGN_RIGHT)
    older_options = [
        ("-1", _("Keep %(number)s (Default)",
                 {"number": config.get(prefs.MAX_OLD_ITEMS_DEFAULT)})),
        ("0", _("Keep 0")),
        ("20", _("Keep 20")),
        ("50", _("Keep 50")),
        ("100", _("Keep 100")),
        ("1000", _("Keep 1000"))
    ]
    older_values = [o[0] for o in older_options]
    older_combo = widgetset.OptionMenu([o[1] for o in older_options])

    if channel.max_old_items == u"system":
        selected = older_values.index("-1")
    else:
        try:
            selected = older_values.index(str(channel.max_old_items))
        except ValueError:
            selected = 0
    older_combo.set_selected(selected)

    def older_changed(widget, index):
        value = older_options[index][0]

        if value == u"system":
            messages.SetFeedMaxOldItems(channel, -1).send_to_backend()
        else:
            messages.SetFeedMaxOldItems(channel, int(value)).send_to_backend()

    older_combo.connect('changed', older_changed)

    button = widgetset.Button(_("Remove All"))
    button.set_size(widgetconst.SIZE_SMALL)

    lab = widgetset.Label("")
    lab.set_size(widgetconst.SIZE_SMALL)
    lab.set_color(widgetconst.DIALOG_NOTE_COLOR)

    def _handle_clicked(widget):
        messages.CleanFeed(channel.id).send_to_backend()
        # FIXME - we don't really know if it got cleaned or if it errored out
        # at this point.  but ...  we need to give some kind of feedback to
        # the user and it's not likely that it failed and if it did, it'd
        # be in the logs.
        lab.set_text(_("Old items have been removed."))
    button.connect('clicked', _handle_clicked)

    grid.pack(older_combo, grid.ALIGN_LEFT)
    grid.pack(button, grid.ALIGN_LEFT)
    grid.end_line(spacing=2)

    grid.pack_label("")
    grid.pack(widgetutil.build_hbox((lab, )), grid.ALIGN_LEFT)

def _build_auto_download(channel, grid):
    auto_download_cbx = widgetset.Checkbox(_("Pause Auto-Downloading when this many items are unplayed:"))
    grid.pack(auto_download_cbx, grid.ALIGN_RIGHT)

    max_new_options = [
        ("1", _("1 unplayed item")),
        ("3", _("3 unplayed items")),
        ("5", _("5 unplayed items")),
        ("10", _("10 unplayed items")),
        ("15", _("15 unplayed items"))
    ]

    max_new_values = [e[0] for e in max_new_options]
    max_new_combo = widgetset.OptionMenu([e[1] for e in max_new_options])

    if channel.max_new == u"unlimited":
        auto_download_cbx.set_checked(False)
        max_new_combo.set_selected(2)
        max_new_combo.disable()
    else:
        auto_download_cbx.set_checked(True)
        value = channel.max_new
        if value < 1:
            value = 1
        else:
            while value not in max_new_values and value > 1:
                value = value - 1
        max_new_combo.set_selected(value)

    def max_new_changed(widget, index):
        value = max_new_options[index][0]
        messages.SetFeedMaxNew(channel, int(value)).send_to_backend()

    def checkbox_changed(widget):
        if widget.get_checked():
            max_new_combo.enable()
            max_new_changed(max_new_combo, 2)
        else:
            max_new_combo.disable()
            max_new_changed(max_new_combo, 2)
            messages.SetFeedMaxNew(channel, u"unlimited").send_to_backend()

    grid.pack(max_new_combo, grid.ALIGN_LEFT)

    max_new_combo.connect('changed', max_new_changed)
    auto_download_cbx.connect('toggled', checkbox_changed)

def run_dialog(channel):
    """Displays the feed settings panel dialog."""
    pref_window = MainDialog(_("Feed Settings"))
    try:
        try:
            v = widgetset.VBox(spacing=10)
            v.pack_start(widgetutil.align_left(_build_header(channel), left_pad=20, right_pad=20))

            v.pack_start(separator.HThinSeparator((0.6, 0.6, 0.6)), padding=18)
            
            grid = dialogwidgets.ControlGrid()
            _build_auto_download(channel, grid)
            grid.end_line(spacing=20)
            _build_video_expires(channel, grid)
            grid.end_line(spacing=20)
            _build_remember_items(channel, grid)
            v.pack_start(widgetutil.align_left(grid.make_table(), left_pad=20, right_pad=20))

            v.pack_end(separator.HThinSeparator((0.6, 0.6, 0.6)), padding=6)

            pref_window.set_extra_widget(v)
            pref_window.add_button(BUTTON_DONE.text)

            pref_window.run()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("feed settings panel threw exception.")
    finally:
        pref_window.destroy()
