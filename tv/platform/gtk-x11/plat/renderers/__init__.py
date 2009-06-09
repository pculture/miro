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

"""miro.plat.renderers -- Classes that render video files."""

import logging
import traceback

from miro import app
from miro import config
from miro.plat import options

def set_renderer(modname):
    """Attempt to set the video renderer."""

    logging.info("set_renderer: trying to add %s", modname)
    try:
        pkg = __import__('miro.plat.renderers.' + modname)
        module = getattr(pkg.plat.renderers, modname)
        app.video_renderer = module.VideoRenderer()
        app.audio_renderer = module.AudioRenderer()
        app.movie_data_program_info = module.movie_data_program_info
        app.get_item_type = module.get_item_type
        logging.info("set_renderer: successfully loaded %s", modname)
    except:
        logging.info("set_renderer: couldn't load %s: %s", modname,
                traceback.format_exc())
        raise

def init_renderer():
    """Initializes a video renderer for us to use.  This call will attempt to
    find a working renderer and set the global variables ``app.audio_renderer``
    and ``app.video_renderer`` to renderers in that module.

    .. Note::

       Renderer modules have to be ``xxxxrenderer`` and ``xxxx`` shows up in
       the preferences.
    """
    r = config.get(options.USE_RENDERER)
    try:
        set_renderer("%srenderer" % r)
        return
    except:
        logging.exception("init_renderer: error detected...  trying to use gstreamerrenderer")

    try:
        # try to add the gstreamer renderer if the preferences aren't right
        set_renderer("gstreamerrenderer")
        return
    except:
        logging.exception("init_renderer: no valid renderer has been loaded")
    app.audio_renderer = None
    app.video_renderer = None
