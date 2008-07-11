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
import glob
import logging

from objc import YES, NO, nil
from Foundation import NSURL
from AppKit import NSColor, NSNotificationCenter
from QTKit import QTMovieView, QTMovie, QTMovieURLAttribute, QTMovieDidEndNotification

from miro.plat import bundle
from miro.plat import qtcomp
from miro.plat.utils import filenameTypeToOSFilename
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets.base import Widget

quicktime_components_registered = False

class VideoRenderer (Widget):

    def __init__(self):
        Widget.__init__(self)
        self.registerQuicktimeComponents()
        self.view = QTMovieView.alloc().initWithFrame_(((0,0),(100,100)))
        self.view.setFillColor_(NSColor.blackColor())
        self.view.setControllerVisible_(NO)
        self.view.setEditable_(NO)
        self.view.setPreservesAspectRatio_(YES)
        self.movie = None
        self.cached_movie = None

    def registerQuicktimeComponents(self):
        global quicktime_components_registered
        if not quicktime_components_registered:
            bundlePath = bundle.getBundlePath()
            componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
            components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
            for component in components:
                cmpName = os.path.basename(component)
                ok = qtcomp.register(component.encode('utf-8'))
                if ok:
                    logging.info('Successfully registered embedded component: %s' % cmpName)
                else:
                    logging.warn('Error while registering embedded component: %s' % cmpName)
        quicktime_components_registered = True

    def calc_size_request(self):
        return (200,200)

    def reset(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.reset')
        if self.view is not nil:
            self.view.setMovie_(nil)
        self.unregister_movie_observer(self.movie)
        self.movie = None
        self.cachedMovie = None
    
    def can_play_movie_file(self, path):
        threads.warn_if_not_on_main_thread('VideoRenderer.can_play_movie_file')
        return True
    
    def set_movie_file(self, path):
        threads.warn_if_not_on_main_thread('VideoRenderer.set_movie_file')
        qtmovie = self.get_movie_from_file(path)
        self.reset()
        if qtmovie is not nil:
            self.movie = qtmovie
            self.view.setMovie_(self.movie)
            self.view.setNeedsDisplay_(YES)
            self.register_movie_observer(qtmovie)

    def get_movie_from_file(self, path):
        osfilename = filenameTypeToOSFilename(path)
        url = NSURL.fileURLWithPath_(osfilename)
        if self.cached_movie is not None and self.cached_movie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cached_movie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
            self.cachedMovie = qtmovie
        return qtmovie

    def register_movie_observer(self, movie):
        threads.warn_if_not_on_main_thread('VideoRenderer.register_movie_observer')
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 'handleMovieNotification:', QTMovieDidEndNotification, movie)

    def unregister_movie_observer(self, movie):
        threads.warn_if_not_on_main_thread('VideoRenderer.unregister_movie_observer')
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, QTMovieDidEndNotification, movie)

    def play(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.play')
        self.view.play_(nil)
        self.view.setNeedsDisplay_(YES)

    def pause(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.pause')
        self.view.pause_(nil)

    def stop(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.stop')
        self.view.pause_(nil)
    
    def handleMovieNotification_(self, notification):
        print notification
