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

"""gstreamerrenderer.py -- Linux gstreamer renderer """

import logging
import os
import sys

import pygst
pygst.require('0.10')
import gst

from miro import app
from miro.frontends.widgets.gst import renderer
from miro.plat import options

# We need to define get_item_type().  Use the version from sniffer.
from miro.frontends.widgets.gst.sniffer import get_item_type

def run_extractor(movie_path, thumbnail_path):
    from miro.plat.renderers import gst_extractor
    return gst_extractor.run(movie_path, thumbnail_path)

class LinuxSinkFactory(renderer.SinkFactory):
    """Linux class to create gstreamer audio/video sinks.

    This class is test for which gstreamer elements we can create and before
    using them.
    """
    def __init__(self):
        self.choose_audiosink()
        self.choose_videosink()

    def choose_audiosink(self):
        """Figure out which audiosink to use.

        After this method, self.audiosink_name will be set to the name of the
        gstreamer element to use for our audiosink.
        """
        audiosink_name = app.config.get(options.GSTREAMER_AUDIOSINK)
        try:
            gst.element_factory_make(audiosink_name, "audiosink")

        except gst.ElementNotFoundError:
            logging.warn("gstreamerrenderer: ElementNotFoundError '%s'",
                         audiosink_name)
            audiosink_name = "autoaudiosink"
            gst.element_factory_make(audiosink_name, "audiosink")

        except Exception, e:
            logging.warn("gstreamerrenderer: Exception thrown '%s'" % e)
            logging.exception("sink exception")
            audiosink_name = "alsasink"
            gst.element_factory_make(audiosink_name, "audiosink")

        logging.info("GStreamer audiosink: %s", audiosink_name)
        self.audiosink_name = audiosink_name

    def choose_videosink(self):
        """Figure out which videosink to use.

        After this method, self.videosink_name will be set to the name of the
        gstreamer element to use for our videosink.
        """
        videosink_name = app.config.get(options.GSTREAMER_IMAGESINK)
        try:
            gst.element_factory_make(videosink_name, "videosink")

        except gst.ElementNotFoundError:
            logging.warn("gstreamerrenderer: ElementNotFoundError '%s'",
                         videosink_name)
            videosink_name = "xvimagesink"
            gst.element_factory_make(videosink_name, "videosink")

        except Exception, e:
            logging.warn("gstreamerrenderer: Exception thrown '%s'" % e)
            logging.exception("sink exception")
            videosink_name = "ximagesink"
            gst.element_factory_make(videosink_name, "videosink")

        logging.info("GStreamer videosink: %s", videosink_name)
        self.videosink_name = videosink_name

    def make_audiosink(self):
        return gst.element_factory_make(self.audiosink_name, "audiosink")

    def make_videosink(self):
        return gst.element_factory_make(self.videosink_name, "videosink")


def make_renderers():
    """Make an audio and video renderer.

    :returns: the tuple (audio_renderer, video_renderer)
    """

    sink_factory = LinuxSinkFactory()
    return (renderer.AudioRenderer(sink_factory),
            renderer.VideoRenderer(sink_factory))
