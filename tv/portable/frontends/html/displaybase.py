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

import logging

from miro import app
from miro import config
from miro import prefs

"""Base class for displays. """

class Display:
    "Base class representing a display in a MainFrame's right-hand pane."

    def __init__(self):
        self.currentFrame = None # tracks the frame that currently has us selected

    def isSelected(self):
        return self.currentFrame is not None

    def onSelected(self, frame):
        "Called when the Display is shown in the given MainFrame."
        pass

    def onDeselected(self, frame):
        """Called when the Display is no longer shown in the given
        MainFrame. This function is called on the Display losing the
        selection before onSelected is called on the Display gaining the
        selection."""
        pass

    def onSelected_private(self, frame):
        assert(self.currentFrame == None)
        self.currentFrame = frame

    def onDeselected_private(self, frame):
        assert(self.currentFrame == frame)
        self.currentFrame = None

    # The MainFrame wants to know if we're ready to display (eg, if the
    # a HTML display has finished loading its contents, so it can display
    # immediately without flicker.) We're to call hook() when we're ready
    # to be displayed.
    def callWhenReadyToDisplay(self, hook):
        hook()

    def cancel(self):
        """Called when the Display is not shown because it is not ready yet
        and another display will take its place"""
        pass

    def getWatchable(self):
        """Subclasses can implement this if they can return a database view
        of watchable items"""
        return None


class VideoDisplayBase (Display):
    """Provides cross platform part of Video Display """
    
    def __init__(self):
        Display.__init__(self)
        self.playbackController = None
        self.volume = 1.0
        self.previousVolume = 1.0
        self.isPlaying = False
        self.isPaused = False
        self.isFullScreen = False
        self.isExternal = False
        self.stopOnDeselect = True
        self.activeRenderer = None

    def initRenderers(self):
        pass

    def setExternal(self, external):
        self.isExternal = external

    def fillMovieData (self, filename, movie_data, callback):
        for renderer in app.renderers:
            success = renderer.fillMovieData(filename, movie_data)
            if success:
                callback ()
                return
        callback ()

    # Override this to call external() if the file cannot be played or
    # set the renderer to the appropriate one it it can be played,
    # then call internal().
    def setRendererAndCallback(self, anItem, internal, external):
        self.setExternal(True)
        external()
        
    def getRendererForItem(self, anItem):
        logging.warn("Using deprecated VideoDisplay.getRendererForItem API. Please, update your code to use setRendererAndCallback().")
        return None
            
    def canPlayItem(self, anItem):
        logging.warn("Using deprecated VideoDisplay.canPlayItem API. Please, update your code.")
        return False
    
    def canPlayFile(self, filename):
        logging.warn("Using deprecated VideoDisplay.canPlayFile API. Please, update your code.")
        return False
    
    def selectItem(self, anItem, renderer):
        from miro.frontends.html.templatedisplay import TemplateDisplay
        self.stopOnDeselect = True
        app.controller.videoInfoItem = anItem
        templ = TemplateDisplay('video-info', 'default')
        area = app.htmlapp.frame.videoInfoDisplay
        app.htmlapp.frame.selectDisplay(templ, area)

        self.setActiveRenderer(renderer)
        self.activeRenderer.selectItem(anItem)
        self.getVolume(lambda vol:self.activeRenderer.setVolume(vol))

    def setActiveRenderer (self, renderer):
        self.activeRenderer = renderer

    def reset(self):
        self.isPlaying = False
        self.isPaused = False
        self.stopOnDeselect = True
        if self.activeRenderer is not None:
            self.activeRenderer.reset()
        self.activeRenderer = None

    def goToBeginningOfMovie(self):
        if self.activeRenderer is not None:
            self.activeRenderer.goToBeginningOfMovie()

    def playPause(self):
        if self.isPlaying:
            self.pause()
        else:
            self.play()

    def playFromTime(self, startTime):
        if self.activeRenderer is not None:
            self.activeRenderer.playFromTime(startTime)
        self.isPlaying = True
        self.isPaused = False

    def play(self):
        if self.activeRenderer is not None:
            self.activeRenderer.play()
        self.isPlaying = True
        self.isPaused = False

    def pause(self):
        if self.activeRenderer is not None:
            self.activeRenderer.pause()
        self.isPlaying = False
        self.isPaused = True

    def stop(self):
        if self.isFullScreen:
            self.exitFullScreen()
        if self.activeRenderer is not None:
            self.activeRenderer.stop()
        self.reset()

    def goFullScreen(self):
        self.isFullScreen = True
        if not self.isPlaying:
            self.play()

    def exitFullScreen(self):
        self.isFullScreen = False

    def getCurrentTime(self, callback):
        if self.activeRenderer is not None:
            self.activeRenderer.getCurrentTime(callback)
        else:
            callback(None)

    def setCurrentTime(self, seconds):
        if self.activeRenderer is not None:
            self.activeRenderer.setCurrentTime(seconds)

    def getProgress(self, callback):
        if self.activeRenderer is not None:
            self.activeRenderer.getProgress(callback)
        else:
            callback(0.0)

    def setProgress(self, progress):
        if self.activeRenderer is not None:
            return self.activeRenderer.setProgress(progress)

    def getDuration(self, callback):
        if self.activeRenderer is not None:
            self.activeRenderer.getDuration(callback)
        else:
            callback(None)

    def setVolume(self, level):
        if level > 1.0:
            level = 1.0
        if level < 0.0:
            level = 0.0
        self.volume = level
        config.set(prefs.VOLUME_LEVEL, level)
        if self.activeRenderer is not None:
            self.activeRenderer.setVolume(level)

    def getVolume(self, callback):
        callback(self.volume)

    def muteVolume(self):
        self.previousVolume = self.volume
        self.setVolume(0.0)

    def restoreVolume(self):
        self.setVolume(self.previousVolume)

    def onDeselected(self, frame):
        if self.stopOnDeselect and (self.isPlaying or self.isPaused):
            app.controller.playbackController.stop(False)
        
