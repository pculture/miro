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
import logging

from miro.frontends.html.templatedisplay import TemplateDisplay
from miro import app
from miro import config
from miro import eventloop
from miro import item
from miro import prefs
from miro import signals
from miro import fileutil

class PlaybackControllerBase:
    
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
        itemSelection = app.selection.itemListSelection
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
            app.htmlapp.displayCurrentTabContent()
    
    def playPause(self):
        videoDisplay = app.htmlapp.videoDisplay
        frame = app.htmlapp.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.playPause()
        else:
            self.enterPlayback()

    def pause(self):
        videoDisplay = app.htmlapp.videoDisplay
        frame = app.htmlapp.frame
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
            while not fileutil.exists(anItem.getVideoFilename()):
                logging.info ("movie file '%s' is missing, skipping to next",
                              anItem.getVideoFilename())
                eventloop.addIdle(self.removeItem, "Remove deleted item", args=(anItem.item,))
                anItem = self.currentPlaylist.getNext()
                if anItem is None:
                    self.stop()
                    return
            self.currentItem = anItem
            if anItem is not None:
                videoDisplay = app.htmlapp.videoDisplay
                videoDisplay.setRendererAndCallback(anItem,lambda :self.playItemInternally(anItem),lambda :self.playItemExternally(anItem))
        except:
            signals.system.failedExn('when trying to play a video')
            self.stop()

    def playItemExternally(self, anItem):
        frame = app.htmlapp.frame
        videoDisplay = app.htmlapp.videoDisplay
        if frame.getDisplay(frame.mainDisplay) is videoDisplay:
            if videoDisplay.isFullScreen:
                videoDisplay.exitFullScreen()
            videoDisplay.stop()
        self.scheduleExternalPlayback(anItem)

    def playItemInternally(self, anItem):
        videoDisplay = app.htmlapp.videoDisplay
        frame = app.htmlapp.frame
        if frame.getDisplay(frame.mainDisplay) is not videoDisplay:
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        if config.get(prefs.RESUME_VIDEOS_MODE) and anItem.resumeTime > 10:
            videoDisplay.playFromTime(anItem.resumeTime)
        else:
            videoDisplay.play()
        self.startUpdateVideoTime()

    def playItemExternallyByID(self, itemID):
        anItem = mapToPlaylistItem(app.db.getObjectByID(int(itemID)))
        app.controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback-continue','default')
        frame = app.htmlapp.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        app.htmlapp.videoDisplay.setExternal(True)
        app.htmlapp.videoDisplay.stopOnDeselect = False
        app.controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback','default')
        frame = app.htmlapp.frame
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
        def actualUpdateVT(t):
            if t != None and self.currentItem:
                self.currentItem.setResumeTime(t)
            if repeat:
                self.updateVideoTimeDC = eventloop.addTimeout(.5, self.updateVideoTime, "Update Video Time")
        app.htmlapp.videoDisplay.getCurrentTime(actualUpdateVT)

    def stop(self, switchDisplay=True, markAsViewed=False):
        app.htmlapp.videoDisplay.setExternal(False)
        if self.updateVideoTimeDC:
            self.updateVideoTime(repeat=False)
            self.stopUpdateVideoTime()
        if self.currentItem:
            self.currentItem.onViewedCancel()
        self.currentItem = None
        frame = app.htmlapp.frame
        videoDisplay = app.htmlapp.videoDisplay
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.stop()
        self.exitPlayback(switchDisplay)

    def skip(self, direction, allowMovieReset=True):
        frame = app.htmlapp.frame
        currentDisplay = frame.getDisplay(frame.mainDisplay)
        def CTCallback(time):
            if time>2.0:
                currentDisplay.goToBeginningOfMovie()
        if self.currentPlaylist is None:
            self.stop()
        elif (allowMovieReset and direction == -1
              and hasattr(currentDisplay, 'getCurrentTime')):
            currentDisplay.getCurrentTime(CTCallback)
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
            frame = app.htmlapp.frame
            currentDisplay = frame.getDisplay(frame.mainDisplay)
            currentDisplay.pause()
            currentDisplay.goToBeginningOfMovie()
            currentDisplay.pause()
        else:
            return self.skip(1, False)

###############################################################################
#### Playlist & Video clips                                                ####
###############################################################################

class Playlist:
    
    def __init__(self, view, firstItemId):
        self.initialView = view
        self.filteredView = self.initialView.filter(mappableToPlaylistItem)
        self.view = self.filteredView.map(mapToPlaylistItem)

        # Move the cursor to the requested item; if there's no
        # such item in the view, move the cursor to the first
        # item
        self.view.confirmDBThread()
        self.view.resetCursor()
        while True:
            cur = self.view.getNext()
            if cur == None:
                # Item not found in view. Put cursor at the first
                # item, if any.
                self.view.resetCursor()
                self.view.getNext()
                break
            if firstItemId is None or cur.getID() == int(firstItemId):
                # The cursor is now on the requested item.
                break

    def reset(self):
        self.initialView.removeView(self.filteredView)
        self.initialView = None
        self.filteredView = None
        self.view = None

    def cur(self):
        return self.itemMarkedAsViewed(self.view.cur())

    def getNext(self):
        return self.itemMarkedAsViewed(self.view.getNext())
        
    def getPrev(self):
        return self.itemMarkedAsViewed(self.view.getPrev())

    def itemMarkedAsViewed(self, anItem):
        if anItem is not None:
            eventloop.addIdle(anItem.onViewed, "Mark item viewed")
        return anItem

class PlaylistItemFromItem:

    def __init__(self, anItem):
        self.item = anItem
        self.dcOnViewed = None

    def getTitle(self):
        return self.item.getTitle()

    def getVideoFilename(self):
        return self.item.getVideoFilename()

    def getLength(self):
        # NEEDS
        return 42.42

    def onViewedExecute(self):
        if self.item.idExists():
            self.item.markItemSeen()
        self.dcOnViewed = None

    def onViewed(self):
        if self.dcOnViewed or self.item.getSeen():
            return
        self.dcOnViewed = eventloop.addTimeout(5, self.onViewedExecute, "Mark item viewed")

    def onViewedCancel(self):
        if self.dcOnViewed:
            self.dcOnViewed.cancel()
            self.dcOnViewed = None

    # Return the ID that is used by a template to indicate this item 
    def getID(self):
        return self.item.getID()

    def __getattr__(self, attr):
        return getattr(self.item, attr)

def mappableToPlaylistItem(obj):
    return (isinstance(obj, item.Item) and obj.isDownloaded())

def mapToPlaylistItem(obj):
    return PlaylistItemFromItem(obj)
