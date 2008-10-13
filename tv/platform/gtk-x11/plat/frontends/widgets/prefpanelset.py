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

"""This module holds functions that extend the panels in the preferences
panel with platform-specific options.

See portable/frontends/widgets/prefpanel.py for more information.
"""

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets.widgetutil import align_left
from miro.frontends.widgets.prefpanel import attach_boolean, attach_radio, attach_combo

from miro.plat import options 

from miro import config

def _general_panel():
    extras = []
    cbx = widgetset.Checkbox(_("Enable tray icon"))
    attach_boolean(cbx, options.SHOW_TRAYICON)
    extras.append(cbx)
    return extras

def _playback_panel():
    extras = []

    lab = widgetset.Label(_("Renderer options:"))
    lab.set_bold(True)
    extras.append(align_left(lab))

    note = dialogwidgets.note(_("You must restart Miro for renderer changes to take effect."))
    extras.append(align_left(note, bottom_pad=12))

    rbg = widgetset.RadioButtonGroup()
    gstreamer_radio = widgetset.RadioButton("gstreamer", rbg)
    xine_radio = widgetset.RadioButton("xine", rbg)
    attach_radio([(gstreamer_radio, "gstreamer"), (xine_radio, "xine")],
                 options.USE_RENDERER)

    grid = dialogwidgets.ControlGrid()
    grid.pack_label(_("Video renderer:"), grid.ALIGN_RIGHT)
    grid.pack(dialogwidgets.radio_button_list(gstreamer_radio, xine_radio))

    viz_options = [("None", _("None")),
                   ("goom", "goom"),
                   ("oscope", "oscope")]
    viz_option_menu = widgetset.OptionMenu([op[1] for op in viz_options])
    attach_combo(viz_option_menu, options.XINE_VIZ, [op[0] for op in viz_options])
    grid.end_line(spacing=12)

    grid.pack_label(_("Use this for video when playing audio:"),
            grid.ALIGN_RIGHT)
    grid.pack(viz_option_menu)

    extras.append(align_left(grid.make_table()))

    def handle_clicked(widget):
        if widget is gstreamer_radio:
            viz_option_menu.disable_widget()
        elif widget is xine_radio:
            viz_option_menu.enable_widget()

    gstreamer_radio.connect('clicked', handle_clicked)
    xine_radio.connect('clicked', handle_clicked)

    if config.get(options.USE_RENDERER) == "gstreamer":
        handle_clicked(gstreamer_radio)
    else:
        handle_clicked(xine_radio)

    return extras

def get_platform_specific(panel_name):
    if panel_name == "general":
        return _general_panel()
    elif panel_name == "playback":
        return _playback_panel()
