# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""miro.plat.options -- Holds platform-specific command line options.
Most/all of these are set in the miro.real script.  The values here are
hopefully sane defaults.
"""

# these have no related prefs
shouldSyncX = False
frontend = 'html'
themeName = None
gconf_name = None

from miro.prefs import Pref

USE_RENDERER = Pref(key="useRenderer",
                    default=u"gstreamer",
                    platformSpecific=False,
                    alias="renderer",
                    help="Which renderer to use.  (gstreamer, xine)" )

USE_XINE_XV_HACK = Pref(key="UseXineXVHack",
                        default=True,
                        platformSpecific=False,
                        alias="xine-xvhack",
                        help="Whether or not to use the Xine xv hack.  (true, false)" )

XINE_DRIVER = Pref(key="DefaultXineDriver",
                   default="xv",
                   platformSpecific=False,
                   alias="xine-driver",
                   help="Which Xine driver to use for video.  (auto, xv, xshm)" )

GSTREAMER_IMAGESINK = Pref(key="DefaultGstreamerImagesink",
                           default="gconfvideosink",
                           platformSpecific=False,
                           alias="gstreamer-imagesink",
                           help="Which GStreamer image sink to use for video.  (autovideosink, ximagesink, xvimagesink, gconfvideosink, ...)")

GSTREAMER_AUDIOSINK = Pref(key="DefaultGstreamerAudiosink",
                           default="gconfaudiosink",
                           platformSpecific=False,
                           alias="gstreamer-audiosink",
                           help="Which GStreamer sink to use for audio.  (autoaudiosink, osssink, alsasink, gconfaudiosink, ...)")


SHOW_TRAYICON = Pref(key="showTrayicon",
                     default=True,
                     platformSpecific=False)

WINDOWS_ICON = Pref(key='windowsIcon',
                    default=None,
                    # this is platform specific, but if we set this to
                    # True then it won't look up the value in the
                    # theme's app.config file
                    platformSpecific=False)

# build a lookup for preferences by alias
PREFERENCES = {}
for mem in dir():
    p = locals()[mem]
    if isinstance(p, Pref) and hasattr(p, "alias"):
        PREFERENCES[p.alias] = p
