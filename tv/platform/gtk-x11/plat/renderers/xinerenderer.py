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

def wait_for_attach(func):
    """Many xine calls can't be made until we attach the object to a X window.
    This decorator delays method calls until then.
    """
    def wait_for_attach_wrapper(self, *args):
        if self.attached:
            func(self, *args)
        else:
            self.attach_queue.append((func, args))
    return wait_for_attach_wrapper

class Renderer:
    def __init__(self):
        logging.info("Xine version:      %s", xine.getXineVersion())
        self.xine = xine.Xine()
        self.xine.set_eos_callback(self.on_eos)
        self.attach_queue = []
        self.attached = False
        self.driver = config.get(options.XINE_DRIVER)
        logging.info("Xine video driver: %s", self.driver)
        self.__playing = False
        self.__volume = 0

    def set_widget(self, widget):
        widget.connect_after("realize", self.on_realize)
        widget.connect("unrealize", self.on_unrealize)
        widget.connect("configure-event", self.on_configure_event)
        widget.connect("expose-event", self.on_expose_event)
        self.widget = widget

    def on_eos(self):
        # on_eos gets called by one of the xine threads, so we want to switch
        # to the ui thread to do things.
        threads.call_on_ui_thread(app.playback_manager.on_movie_finished)

    def on_realize(self, widget):
        # flush gdk output to ensure that our window is created
        gtk.gdk.flush()
        displayName = gtk.gdk.display_get_default().get_name()
        self.xine.attach(displayName,
                         widget.window.xid,
                         self.driver,
                         int(options.shouldSyncX),
                         int(config.get(options.USE_XINE_XV_HACK)))
        self.attached = True
        for func, args in self.attach_queue:
            try:
                func(self, *args)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.exception("Exception in attach_queue function")
        self.attach_queue = []

    def on_unrealize(self, widget):
        self.xine.detach()
        self.attached = False

    def on_configure_event(self, widget, event):
        self.xine.set_area(event.x, event.y, event.width, event.height)

    def on_expose_event(self, widget, event):
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

    def select_item(self, an_item):
        self.select_file(an_item.get_filename())

    @wait_for_attach
    def select_file(self, filename):
        viz = config.get(options.XINE_VIZ)
        self.xine.set_viz(viz)
        self.xine.select_file(filename)
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

    @wait_for_attach
    def seek(self, seconds):
        # this is really funky.  what's going on here is that xine-lib doesn't
        # provide a way to seek while paused.  if you seek, then it induces
        # playing, but that's not what we want.
        # so we do this sneaky thing where if we're paused, we shut the volume
        # off, seek, pause, and turn the volume back on.  that allows us to
        # seek, remain paused, and doesn't cause a hiccup in sound.

        if self.__playing:
            self.xine.seek(int(seconds * 1000))

        else:
            self.xine.set_volume(0)
            self.xine.seek(int(seconds * 1000))
            self.pause()
            self.set_volume(self.__volume)

    def get_duration(self):
        try:
            pos, length = self.xine.get_position_and_length()
            return length / 1000.0
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("get_duration: caught exception")

    @wait_for_attach
    def set_volume(self, level):
        self.__volume = level
        self.xine.set_volume(int(level * 100))

    @wait_for_attach
    def play(self):
        self.xine.play()
        self.__playing = True

    @wait_for_attach
    def pause(self):
        if self.__playing:
            self.xine.pause()
            self.__playing = False

    stop = pause
    reset = pause

    def get_rate(self):
        # FIXME - there's no get_rate
        return self.xine.get_rate()

    @wait_for_attach
    def set_rate(self, rate):
        # FIXME - there's no set_rate
        self.xine.set_rate(rate)

    def movie_data_program_info(self, movie_path, thumbnail_path):
        if os.path.exists(resources.path('../../../lib/miro/xine_extractor')):
            path = resources.path('../../../lib/miro/xine_extractor')
        else:
            logging.error("xine_extractor cannot be found.")
        return ((path, movie_path, thumbnail_path), None)
