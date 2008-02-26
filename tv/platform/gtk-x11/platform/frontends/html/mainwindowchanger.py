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

import gtk
from miro import app
import gobject
from miro.platform.utils import confirmMainThread
import logging

class MainWindowChanger(object):
    """Change which widgets are visible in the main window based on its
    current state.  The following states are possible:

    BROWSING -- Browsing a page with lots of feed links, like the
            Channel Guide.  Disable all video controls.
    PLAYLIST -- Viewing a page with a video playlist.  Only enable the play
            button.
    VIDEO -- Playing a video.  Enable all video controls.
    VIDEO_FULLSCREEN -- Playing a video in fullscreen, make the window
        fullscreen and only show the video playback controls.
    VIDEO_ONLY_FULLSCREEN -- Playing a video in fullscreen and the user
        hasn't moved the mouse in a while.  Only show the video output.

    Member variables:

    currentState -- Currently selected state, will be one of the constants
        listed above.
    """

    BROWSING = 1
    PLAYLIST = 2
    VIDEO = 3

    def __init__(self, widgetTree, mainFrame, initialState):
        confirmMainThread()
        self.widgetTree = widgetTree
        self.mainFrame = mainFrame
        self.currentState = None
        self.isFullScreen = False
        self.wasFullScreen = False
        self.pointerIdle = False
        self.timeoutId = None
        self.motionHandlerId = None
        self.hideDelay = 3000
        self.enablePointerTracking()
        self.createCursor()
        self.changeState(initialState)

    def createCursor(self):
        confirmMainThread()
        pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
        color = gtk.gdk.Color()
        self.empty_cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)

    def updatePlayPauseButton(self):
        """Update the play/pause button to have the correct image."""
        confirmMainThread()
        playPauseImage = self.widgetTree['play-pause-image']
        if app.htmlapp.videoDisplay.isPlaying:
            pixbuf = playPauseImage.render_icon(gtk.STOCK_MEDIA_PAUSE, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
            self.mainFrame.actionGroups["VideoPlayable"].get_action ("PlayPauseVideo").set_property("label", "_Pause")
            self.mainFrame.actionGroups["VideoPlayable"].get_action ("PlayPauseVideo").set_property("stock-id", gtk.STOCK_MEDIA_PAUSE)
        else:
            pixbuf = playPauseImage.render_icon(gtk.STOCK_MEDIA_PLAY, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
            self.mainFrame.actionGroups["VideoPlayable"].get_action ("PlayPauseVideo").set_property("label", "_Play")
            self.mainFrame.actionGroups["VideoPlayable"].get_action ("PlayPauseVideo").set_property("stock-id", gtk.STOCK_MEDIA_PLAY)
        playPauseImage.set_from_pixbuf(pixbuf)

    def updateFullScreenButton(self):
        confirmMainThread()
        fullscreenImage = self.widgetTree['fullscreen-image']
        try:
            if self.isFullScreen and self.currentState == self.VIDEO:
                pixbuf = fullscreenImage.render_icon(gtk.STOCK_LEAVE_FULLSCREEN,
                                                     gtk.ICON_SIZE_LARGE_TOOLBAR)
            else:
                pixbuf = fullscreenImage.render_icon(gtk.STOCK_FULLSCREEN,
                                                     gtk.ICON_SIZE_LARGE_TOOLBAR)
            fullscreenImage.set_from_pixbuf(pixbuf)
        except:
            pass

    def setVideoWidgetsSensitive(self, sensitive):
        """Enable/disable widgets that only make sense to use when we're
        playing a video.
        """

        confirmMainThread()

        videoWidgets = ['play-pause-button',
            'next-button', 'previous-button', 'fullscreen-button',
            'video-time-scale']
        # delete-video should be in this list, but it's not implemented yet
        for widget in videoWidgets:
            self.widgetTree[widget].set_sensitive(sensitive)
        self.mainFrame.actionGroups["VideoPlaying"].set_sensitive (sensitive)

    def updateState (self):
        # Handle fullscreen
        confirmMainThread()
        try:
            fullscreen = (self.isFullScreen and self.currentState == self.VIDEO)
            activeRenderer = app.htmlapp.videoDisplay.activeRenderer
            if fullscreen and (not self.wasFullScreen):
                self.widgetTree['main-window'].fullscreen()
                if activeRenderer != None:
                    activeRenderer.goFullscreen()
                self.wasFullScreen = True
            if (not fullscreen) and self.wasFullScreen:
                self.widgetTree['main-window'].unfullscreen()
                if activeRenderer != None:
                    activeRenderer.exitFullscreen()
                self.wasFullScreen = False
            self.updateFullScreenButton()

            # Hide cursor
            if fullscreen and self.currentState == self.VIDEO and self.pointerIdle:
                # Hide cursor
                self.widgetTree["main-box"].window.set_cursor (self.empty_cursor)
            else:
                # Show cursor
                self.widgetTree["main-box"].window.set_cursor (None)

            # Handle UI visibility and sensitivity
            if self.currentState == self.BROWSING:
                self.widgetTree['channels-box'].show()
                self.widgetTree['video-info-box'].hide()
                self.widgetTree['video-control-box'].show()
                self.widgetTree['menubar-box'].show()
                self.setVideoWidgetsSensitive(False)
            elif self.currentState == self.PLAYLIST:
                self.widgetTree['channels-box'].show()
                self.widgetTree['video-info-box'].hide()
                self.widgetTree['video-control-box'].show()
                self.widgetTree['menubar-box'].show()
                self.setVideoWidgetsSensitive(False)
                self.widgetTree['play-pause-button'].set_sensitive(True)
            elif self.currentState == self.VIDEO:
                if self.isFullScreen:
                    if self.pointerIdle:
                        self.widgetTree['channels-box'].hide()
                        self.widgetTree['video-info-box'].hide()
                        self.widgetTree['video-control-box'].hide()
                        self.widgetTree['menubar-box'].hide()
                        self.setVideoWidgetsSensitive(True)
                    else:
                        self.widgetTree['channels-box'].hide()
                        self.widgetTree['video-info-box'].show()
                        self.widgetTree['video-control-box'].show()
                        self.widgetTree['menubar-box'].hide()
                        self.setVideoWidgetsSensitive(True)
                else:
                    self.widgetTree['channels-box'].show()
                    self.widgetTree['video-info-box'].show()
                    self.widgetTree['video-control-box'].show()
                    self.widgetTree['menubar-box'].show()
                    self.setVideoWidgetsSensitive(True)
            else:
                raise TypeError("invalid state: %r" % newState)
            self.updatePlayPauseButton()
            self.mainFrame.onVideoLoadedChange (self.currentState == self.VIDEO)
        except AttributeError:
            logging.warn("Display updated before video display was created")

    def enablePointerTracking(self):
        confirmMainThread()
        self.disablePointerTracking()
        self.motionHandlerId = self.widgetTree['main-window'].connect(
                'motion-notify-event', self.onMotion)
        self.resetTimer()

    def disablePointerTracking(self):
        confirmMainThread()
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
            self.timeoutId = None
        if self.motionHandlerId is not None:
            self.widgetTree['main-window'].disconnect(self.motionHandlerId)
            self.motionHandlerId = None

    def resetTimer(self):
        confirmMainThread()
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
        self.timeoutId = gobject.timeout_add(self.hideDelay, self.onTimeout)

    def onTimeout(self):
        confirmMainThread()
        self.pointerIdle = True
        self.timeoutId = None
        self.updateState()
        return False

    def onMotion(self, window, event):
        confirmMainThread()
        self.pointerIdle = False
        self.resetTimer()
        self.updateState()
        return False

    def changeFullScreen (self, fullscreen):
        confirmMainThread()
        
        # Get window XID (needed for xdg-screensaver)
        win = self.widgetTree['main-window'];
        xid = win.window.xid
        
        if (self.isFullScreen == fullscreen):
            return
        if fullscreen:
            cmd = "xdg-screensaver suspend 0x%X" % (xid)
        else:
            cmd = "xdg-screensaver resume 0x%X" % (xid)
        rv = os.system(cmd)
        if rv != 0:
            print "WARNING: %s returned %s" % (cmd, rv)

        self.isFullScreen = fullscreen
        self.updateState()

    def changeState(self, newState):
        confirmMainThread()
        if newState == self.currentState:
            return
        self.currentState = newState
        self.updateState()
