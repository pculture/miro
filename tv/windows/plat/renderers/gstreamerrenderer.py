# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""gstreamerrenderer.py -- Windows gstreamer renderer """

# Before importing gstreamer, fix os.environ so gstreamer finds it's plugins
import os
from miro.plat import resources
GST_PLUGIN_PATH = os.path.join(resources.app_root(), 'gstreamer-0.10')
os.environ["GST_PLUGIN_PATH"] = GST_PLUGIN_PATH
os.environ["GST_PLUGIN_SYSTEM_PATH"] = GST_PLUGIN_PATH

import pygst
pygst.require('0.10')
import gst

from miro import app
from miro.frontends.widgets.gst import renderer

# We need to define get_item_type().  Use the version from sniffer.
from miro.frontends.widgets.gst.sniffer import get_item_type

class WindowsSinkFactory(renderer.SinkFactory):
    """Windows class to create gstreamer audio/video sinks.

    This class is very simple because we know exactly what gstreamer plugins
    we install on windows.
    """

    def make_audiosink(self):
        return gst.element_factory_make("directsoundsink" , "audiosink")

    def make_videosink(self):
        # Use dshowvideosink.
        # d3dvideosink doesn't work on my vmware VM.
        # directdrawsink does work, but I believe it is less likely to be
        # hardware accelerated than the direct show one.
        return gst.element_factory_make("dshowvideosink" , "videosink")

def make_renderers():
    sink_factory = WindowsSinkFactory()
    return (renderer.AudioRenderer(sink_factory),
            renderer.VideoRenderer(sink_factory))
