# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

from miro.plat import renderers
from miro.plat import options 

from miro import config, prefs

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

    grid = dialogwidgets.ControlGrid()

    note = dialogwidgets.note(_("You must restart %(appname)s for renderer "
                                "changes to take effect.",
                                {"appname": config.get(prefs.SHORT_APP_NAME)}))
    grid.pack(align_left(note, bottom_pad=12), grid.ALIGN_LEFT, span=2)

    grid.end_line(spacing=12)

    rbg = widgetset.RadioButtonGroup()
    radio_map = {}
    for mem in renderers.get_renderer_list():
        radio_map[mem] = widgetset.RadioButton(mem, rbg)

    buttons = [(v, k) for k, v in radio_map.items()]
    attach_radio(buttons, options.USE_RENDERER)

    grid.pack_label(_("Video renderer:"), grid.ALIGN_RIGHT)
    grid.pack(dialogwidgets.radio_button_list(*radio_map.values()))

    grid.end_line(spacing=12)

    extras.append(align_left(grid.make_table()))

    return extras

def get_platform_specific(panel_name):
    if panel_name == "general":
        return _general_panel()
    elif panel_name == "playback":
        if len(renderers.get_renderer_list()) > 1:
            return _playback_panel()
