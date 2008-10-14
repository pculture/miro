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

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.plat import options
from miro.frontends.widgets.prefpanel import attach_boolean, attach_radio
from miro.frontends.widgets.widgetutil import align_left
from miro import prefs

def _general_panel():
    extras = []
    show_cbx = widgetset.Checkbox(_("Enable tray icon"))
    attach_boolean(show_cbx, options.SHOW_TRAYICON)
    extras.append(show_cbx)

    lab = widgetset.Label(_("When I click the red close button:"))
    extras.append(align_left(lab))
    rbg = widgetset.RadioButtonGroup()
    rad_close = widgetset.RadioButton(_("Close to tray so that downloads can continue."), rbg)
    rad_quit = widgetset.RadioButton(_("Quit Miro completely."), rbg)

    attach_radio([(rad_close, True), (rad_quit, False)], prefs.MINIMIZE_TO_TRAY)
    extras.append(align_left(rad_close, left_pad=20))
    extras.append(align_left(rad_quit, left_pad=20))
    return extras

def get_platform_specific(panel_name):
    if panel_name == "general":
        return _general_panel()
