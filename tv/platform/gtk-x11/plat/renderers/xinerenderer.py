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

import os.path
import logging

import gtk
import gobject

from miro import app
from miro import config
from miro import xine
from miro.plat import options
from miro.plat import resources
from miro.plat.frontends.widgets import threads

class Renderer:
    def __init__(self):
        logging.info("Xine version:      %s", xine.getXineVersion())
        self.xine = xine.Xine()
        self.xine.set_eos_callback(self.on_eos)
        self.driver = config.get(options.XINE_DRIVER)
        logging.info("Xine video driver: %s", self.driver)
        self._playing = False
        self._volume = 0

    def set_widget(self, widget):
        widget.connect("destroy", self.on_destroy)
        widget.connect("configure-event", self.on_configure_event)
        widget.connect("expose-event", self.on_expose_event)
        self.widget = widget

        # flush gdk output to ensure that the window we're passing to xine has
        # been created
        gtk.gdk.flush()
        displayName = gtk.gdk.display_get_default().get_name()
        self.xine.attach(displayName,
                         widget.persistent_window.xid,
                         self.driver,
                         int(options.shouldSyncX),
                         int(config.get(options.USE_XINE_XV_HACK)))
        self.gc = widget.persistent_window.new_gc()
        self.gc.foreground = gtk.gdk.color_parse("black")

    def on_eos(self):
        # on_eos gets called by one of the xine threads, so we want to switch
        # to the ui thread to do things.
        threads.call_on_ui_thread(app.playback_manager.on_movie_finished)

    def on_destroy(self, widget):
        self.xine.detach()

    def on_configure_event(self, widget, event):
        self.xine.set_area(event.x, event.y, event.width, event.height)

    def on_expose_event(self, widget, event):
        # if we wanted to draw an image for audio-only items, this is where
        # we'd do it.
        widget.window.draw_rectangle(self.gc,
                                     True,
                                     0, 0,
                                     widget.allocation.width,
                                     widget.allocation.height)
        self.xine.got_expose_event(event.area.x, event.area.y, event.area.width,
                event.area.height)

    def can_play_file(self, filename, yes_callback, no_callback):
        if self.xine.can_play_file(filename):
            yes_callback()
        else:
            no_callback()

    def go_fullscreen(self):
        """Handle when the video window goes fullscreen."""
        # Sometimes xine doesn't seem to handle the expose events properly and
        # only thinks part of the window is exposed.  To work around this we
        # send it a couple of fake expose events for the entire window, after
        # a short time delay.

        def fullscreen_expose_workaround():
            try:
                _, _, width, height, _ = self.widget.window.get_geometry()
                self.xine.got_expose_event(0, 0, width, height)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                return True
            return False

        gobject.timeout_add(500, fullscreen_expose_workaround)
        gobject.timeout_add(1000, fullscreen_expose_workaround)

    def exit_fullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        # nothing to do here
        pass

    def change_visualization(self, value):
        pass

    def select_file(self, filename, callback, errback):
        self._filename = filename
        viz = config.get(options.VIZ_PLUGIN)
        self.xine.set_viz(viz)
        if self.xine.select_file(filename):
            gobject.idle_add(callback)
            def expose_workaround():
                try:
                    _, _, width, height, _ = self.widget.window.get_geometry()
                    self.xine.got_expose_event(0, 0, width, height)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    return True
                return False

            gobject.timeout_add(500, expose_workaround)
            self.seek(0)
        else:
            gobject.idle_add(errback)

    def get_progress(self):
        try:
            pos, length = self.xine.get_position_and_length()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.warn("get_current_time: caught exception: %s" % e)
            return None

    def get_current_time(self):
        try:
            pos, length = self.xine.get_position_and_length()
            return pos / 1000.0
        except Exception, e:
            logging.warn("get_current_time: caught exception: %s" % e)
            return None

    def set_current_time(self, seconds):
        self.seek(seconds)

    def seek(self, seconds):
        # this is really funky.  what's going on here is that xine-lib doesn't
        # provide a way to seek while paused.  if you seek, then it induces
        # playing, but that's not what we want.
        # so we do this sneaky thing where if we're paused, we shut the volume
        # off, seek, pause, and turn the volume back on.  that allows us to
        # seek, remain paused, and doesn't cause a hiccup in sound.

        if self._playing:
            self.xine.seek(int(seconds * 1000))

        else:
            self._playing = True
            self.xine.set_volume(0)
            self.xine.seek(int(seconds * 1000))
            self.pause()
            self.set_volume(self._volume)

    def get_duration(self):
        try:
            pos, length = self.xine.get_position_and_length()
            return length / 1000.0
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("get_duration: caught exception")

    def set_volume(self, level):
        self._volume = level
        self.xine.set_volume(int(level * 100))

    def play(self):
        self.xine.play()
        self._playing = True

    def pause(self):
        if self._playing:
            self.xine.pause()
            self._playing = False

    stop = pause
    reset = pause

    def get_rate(self):
        logging.warn("get_rate not implemented for xine")

    def set_rate(self, rate):
        logging.warn("set_rate not implemented for xine")

    def movie_data_program_info(self, movie_path, thumbnail_path):
        if os.path.exists(resources.path('./../../lib/miro/xine_extractor')):
            path = resources.path('../../../lib/miro/xine_extractor')
            return ((path, movie_path, thumbnail_path), None)
        else:
            logging.error("xine_extractor cannot be found.")
            raise NotImplementedError()
