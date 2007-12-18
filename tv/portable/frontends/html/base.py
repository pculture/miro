# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""frontends.html.display.  Base classes for Displays.  This module contains
base clases that are subclassed in the platform specific code.
"""

import config
import prefs

class PlaybackControllerBase:
    """The Playback Controller base class."""
    
    def __init__(self):
        self.currentPlaylist = None
        self.justPlayOne = False
        self.currentItem = None
        self.updateVideoTimeDC = None

    def configure(self, view, firstItemId=None, justPlayOne=False):
        self.currentPlaylist = Playlist(view, firstItemId)
        self.justPlayOne = justPlayOne
    
    def reset(self):
        if self.currentPlaylist is not None:
            eventloop.addIdle (self.currentPlaylist.reset, "Reset Playlist")
            self.currentPlaylist = None

    def configureWithSelection(self):
        itemSelection = controller.selection.itemListSelection
        view = itemSelection.currentView
        if itemSelection.currentView is None:
            return

        for item in view:
            itemid = item.getID()
            if itemSelection.isSelected(view, itemid) and item.isDownloaded():
                self.configure(view, itemid)
                break
    
    def enterPlayback(self):
        if self.currentPlaylist is None:
            self.configureWithSelection()
        if self.currentPlaylist is not None:
            startItem = self.currentPlaylist.cur()
            if startItem is not None:
                self.playItem(startItem)
        
    def exitPlayback(self, switchDisplay=True):
        self.reset()
        if switchDisplay:
            controller.selection.displayCurrentTabContent()
    
    def playPause(self):
        videoDisplay = controller.videoDisplay
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.playPause()
        else:
            self.enterPlayback()

    def pause(self):
        videoDisplay = controller.videoDisplay
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.pause()

    def removeItem(self, item):
        if item.idExists():
            item.executeExpire()

    def playItem(self, anItem):
        try:
            if self.currentItem:
                self.currentItem.onViewedCancel()
            self.currentItem = None
            while not os.path.exists(anItem.getVideoFilename()):
                logging.info ("movie file '%s' is missing, skipping to next",
                              anItem.getVideoFilename())
                eventloop.addIdle(self.removeItem, "Remove deleted item", args=(anItem.item,))
                anItem = self.currentPlaylist.getNext()
                if anItem is None:
                    self.stop()
                    return

            self.currentItem = anItem
            if anItem is not None:
                videoDisplay = controller.videoDisplay
                videoRenderer = videoDisplay.getRendererForItem(anItem)
                if videoRenderer is not None:
                    self.playItemInternally(anItem, videoDisplay, videoRenderer)
                else:
                    frame = controller.frame
                    if frame.getDisplay(frame.mainDisplay) is videoDisplay:
                        if videoDisplay.isFullScreen:
                            videoDisplay.exitFullScreen()
                        videoDisplay.stop()
                    self.scheduleExternalPlayback(anItem)
        except:
            signals.system.failedExn('when trying to play a video')
            self.stop()

    def playItemInternally(self, anItem, videoDisplay, videoRenderer):
        logging.info("Playing item with renderer: %s" % videoRenderer)
        controller.videoDisplay.setExternal(False)
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) is not videoDisplay:
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        videoDisplay.selectItem(anItem, videoRenderer)
        if config.get(prefs.RESUME_VIDEOS_MODE) and anItem.resumeTime > 10:
            videoDisplay.playFromTime(anItem.resumeTime)
        else:
            videoDisplay.play()
        self.startUpdateVideoTime()

    def playItemExternally(self, itemID):
        anItem = mapToPlaylistItem(db.getObjectByID(int(itemID)))
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback-continue','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        controller.videoDisplay.setExternal(True)
        controller.videoDisplay.stopOnDeselect = False
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        anItem.markItemSeen()

    def startUpdateVideoTime(self):
        if not self.updateVideoTimeDC:
            self.updateVideoTimeDC = eventloop.addTimeout(.5, self.updateVideoTime, "Update Video Time")

    def stopUpdateVideoTime(self):
        if self.updateVideoTimeDC:
            self.updateVideoTimeDC.cancel()
            self.updateVideoTimeDC = None

    def updateVideoTime(self, repeat=True):
        t = controller.videoDisplay.getCurrentTime()
        if t != None and self.currentItem:
            self.currentItem.setResumeTime(t)
        if repeat:
            self.updateVideoTimeDC = eventloop.addTimeout(.5, self.updateVideoTime, "Update Video Time")

    def stop(self, switchDisplay=True, markAsViewed=False):
        controller.videoDisplay.setExternal(False)
        if self.updateVideoTimeDC:
            self.updateVideoTime(repeat=False)
            self.stopUpdateVideoTime()
        if self.currentItem:
            self.currentItem.onViewedCancel()
        self.currentItem = None
        frame = controller.frame
        videoDisplay = controller.videoDisplay
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.stop()
        self.exitPlayback(switchDisplay)

    def skip(self, direction, allowMovieReset=True):
        frame = controller.frame
        currentDisplay = frame.getDisplay(frame.mainDisplay)
        if self.currentPlaylist is None:
            self.stop()
        elif (allowMovieReset and direction == -1
                and hasattr(currentDisplay, 'getCurrentTime') 
                and currentDisplay.getCurrentTime() > 2.0):
            currentDisplay.goToBeginningOfMovie()
        elif config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE) or self.justPlayOne:
            self.stop()
        else:
            if direction == 1:
                nextItem = self.currentPlaylist.getNext()
            else:
                nextItem = self.currentPlaylist.getPrev()
            if nextItem is None:
                self.stop()
            else:
                if self.updateVideoTimeDC:
                    self.updateVideoTime(repeat=False)
                    self.stopUpdateVideoTime()
                self.playItem(nextItem)

    def onMovieFinished(self):
        self.stopUpdateVideoTime()
        setToStart = False
        if self.currentItem:
            self.currentItem.setResumeTime(0)
            if self.currentItem.getFeedURL() == 'dtv:singleFeed':
                setToStart = True
        if setToStart:
            frame = controller.frame
            currentDisplay = frame.getDisplay(frame.mainDisplay)
            currentDisplay.pause()
            currentDisplay.goToBeginningOfMovie()
            currentDisplay.pause()
        else:
            return self.skip(1, False)

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
    """Provides cross platform part of video display."""
    
    def __init__(self):
        Display.__init__(self)
        self.playbackController = None
        self.volume = 1.0
        self.previousVolume = 1.0
        self.isPlaying = False
        self.isFullScreen = False
        self.isExternal = False
        self.stopOnDeselect = True
        self.renderers = list()
        self.activeRenderer = None

    def initRenderers(self):
        pass

    def setExternal(self, external):
        self.isExternal = external

    def fillMovieData (self, filename, movie_data, callback):
        for renderer in self.renderers:
            success = renderer.fillMovieData(filename, movie_data)
            if success:
                callback ()
                return
        callback ()
        
    def getRendererForItem(self, anItem):
        for renderer in self.renderers:
            if renderer.canPlayItem(anItem):
                return renderer
        return None

    def canPlayItem(self, anItem):
        return self.getRendererForItem(anItem) is not None
    
    def canPlayFile(self, filename):
        for renderer in self.renderers:
            if renderer.canPlayFile(filename):
                return True
        return False
    
    def selectItem(self, anItem, renderer):
        self.stopOnDeselect = True
        controller.videoInfoItem = anItem
        templ = TemplateDisplay('video-info', 'default')
        area = controller.frame.videoInfoDisplay
        controller.frame.selectDisplay(templ, area)

        self.setActiveRenderer(renderer)
        self.activeRenderer.selectItem(anItem)
        self.activeRenderer.setVolume(self.getVolume())

    def setActiveRenderer (self, renderer):
        self.activeRenderer = renderer

    def reset(self):
        self.isPlaying = False
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

    def play(self):
        if self.activeRenderer is not None:
            self.activeRenderer.play()
        self.isPlaying = True

    def pause(self):
        if self.activeRenderer is not None:
            self.activeRenderer.pause()
        self.isPlaying = False

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

    def getCurrentTime(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getCurrentTime()
        return None

    def setCurrentTime(self, seconds):
        if self.activeRenderer is not None:
            self.activeRenderer.setCurrentTime(seconds)

    def getProgress(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getProgress()
        return 0.0

    def setProgress(self, progress):
        if self.activeRenderer is not None:
            return self.activeRenderer.setProgress(progress)

    def getDuration(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getDuration()
        return None

    def setVolume(self, level):
        if level > 1.0:
            level = 1.0
        if level < 0.0:
            level = 0.0
        self.volume = level
        config.set(prefs.VOLUME_LEVEL, level)
        if self.activeRenderer is not None:
            self.activeRenderer.setVolume(level)

    def getVolume(self):
        return self.volume

    def muteVolume(self):
        self.previousVolume = self.getVolume()
        self.setVolume(0.0)

    def restoreVolume(self):
        self.setVolume(self.previousVolume)

    def onDeselected(self, frame):
        if self.isPlaying and self.stopOnDeselect:
            controller.playbackController.stop(False)
