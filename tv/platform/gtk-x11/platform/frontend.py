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

import os
from miro import config
from miro import prefs
# Switch to a dummy frontend in the case we're running tests and
# DISPLAY isn't set
try:
    import gtk
    hasGTK = True
except ImportError:
    print "DTV: Warning: could not import GTK (is DISPLAY set?)"
    hasGTK = False

if hasGTK:
    # Import MozillaBrowser ASAP.  On some systems the gtkmozembed
    # module is linked against a different libxpcom than
    # MozillaBrowser.  Importing it first ensures that
    # MozillaBrowser's libxpcom gets linked to.
    #
    # NOTE: this could also lead to problems, since now gtkmozembed is
    # being linked to a different libxpcom than it expects.  This way
    # seems to be less bad though, so we'll use it for now.  See Bug
    # #1560.
    from miro.platform import MozillaBrowser

    # Almost everything is split out into files under
    # frontend-implementation.
    from miro.frontend_implementation.Application import Application
    from miro.frontend_implementation.MainFrame import MainFrame
    from miro.frontend_implementation.UIBackendDelegate import UIBackendDelegate
    from miro.frontend_implementation.VideoDisplay import VideoDisplay
    from miro.frontend_implementation.VideoDisplay import PlaybackController
else:
    class Application:
        pass
    class MainFrame:
        pass
    class NullDisplay:
        pass
    class UIBackendDelegate:
        pass
    class HTMLDisplay:
        pass
    class VideoDisplay:
        pass
    class PlaybackController:
        pass

###############################################################################
###############################################################################
