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

"""video.py -- Video code. """

import logging
import traceback

import gtk

from miro import app
from miro import config
from miro.frontends.widgets.gtk.widgetset import Widget
from miro.plat import options
from miro.plat.utils import confirmMainThread

def set_renderer(modname):
    """Attempt to set the video renderer."""

    logging.info("set_renderer: trying to add %s", modname)
    try:
        pkg = __import__('miro.plat.renderers.' + modname)
        module = getattr(pkg.plat.renderers, modname)
        app.renderer = module.Renderer()
        logging.info("set_renderer: successfully loaded %s", modname)
    except:
        logging.info("set_renderer: couldn't load %s: %s", modname,
                traceback.format_exc())
        raise

def init_renderer():
    """Initializes a video renderer for us to use.

    Note: renderer modules have to be xxxxrenderer and xxxx shows up in the
    preferences.
    """
    r = config.get(options.USE_RENDERER)
    try:
        set_renderer("%srenderer" % r)
    except:
        try:
            logging.error("init_renderer: error detected...  trying to add gstreamerrenderer")

            # try to add the gstreamer renderer if the preferences aren't right
            set_renderer("gstreamerrenderer")
        except:
            logging.error("init_renderer: no valid renderer has been loaded")
        app.renderer = None

class VideoRenderer (Widget):

    def __init__(self):
        Widget.__init__(self)
        self.renderer = app.renderer
        self.set_widget(gtk.DrawingArea())
        self._widget.set_double_buffered(False)
        self._widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.renderer.setWidget(self._widget)

    def reset(self):
        confirmMainThread()
        self.renderer.reset()
    
    def can_play_movie_file(self, path):
        confirmMainThread()
        return self.renderer.canPlayFile(anItem.getVideoFilename())
    
    def set_movie_file(self, path):
        confirmMainThread()
        self.renderer.selectFile(path)

    def play(self):
        confirmMainThread()
        self.renderer.play()

    def pause(self):
        confirmMainThread()
        self.renderer.pause()

    def stop(self):
        confirmMainThread()
        self.renderer.stop()
