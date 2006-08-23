import os

import gtk
import app
import gobject
import platformutils

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
        platformutils.confirmMainThread()
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
        platformutils.confirmMainThread()
        pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
        color = gtk.gdk.Color()
        self.empty_cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)

    def updatePlayPauseButton(self):
        """Update the play/pause button to have the correct image."""
        platformutils.confirmMainThread()
        playPauseImage = self.widgetTree['play-pause-image']
        if app.controller.videoDisplay.isPlaying:
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
        platformutils.confirmMainThread()
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

        platformutils.confirmMainThread()

        videoWidgets = ['play-pause-button',
            'next-button', 'previous-button', 'fullscreen-button',
            'video-time-scale']
        # delete-video should be in this list, but it's not implemented yet
        for widget in videoWidgets:
            self.widgetTree[widget].set_sensitive(sensitive)
        self.mainFrame.actionGroups["VideoPlaying"].set_sensitive (sensitive)

    def updateState (self):
        # Handle fullscreen
        platformutils.confirmMainThread()
        fullscreen = (self.isFullScreen and self.currentState == self.VIDEO)
        activeRenderer = app.controller.videoDisplay.activeRenderer
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

    def enablePointerTracking(self):
        platformutils.confirmMainThread()
        self.disablePointerTracking()
        self.motionHandlerId = self.widgetTree['main-window'].connect(
                'motion-notify-event', self.onMotion)
        self.resetTimer()

    def disablePointerTracking(self):
        platformutils.confirmMainThread()
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
            self.timeoutId = None
        if self.motionHandlerId is not None:
            self.widgetTree['main-window'].disconnect(self.motionHandlerId)
            self.motionHandlerId = None

    def resetTimer(self):
        platformutils.confirmMainThread()
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
        self.timeoutId = gobject.timeout_add(self.hideDelay, self.onTimeout)

    def onTimeout(self):
        platformutils.confirmMainThread()
        self.pointerIdle = True
        self.timeoutId = None
        self.updateState()
        return False

    def onMotion(self, window, event):
        platformutils.confirmMainThread()
        self.pointerIdle = False
        self.resetTimer()
        self.updateState()
        return False

    def changeFullScreen (self, fullscreen):
        platformutils.confirmMainThread()
        if (self.isFullScreen == fullscreen):
            return
        if fullscreen:
            cmd = "xset s off"
        else:
            cmd = "xset s"
        rv = os.system(cmd)
        if rv != 0:
            print "WARNING: %s returned %s" % (cmd, rv)

        self.isFullScreen = fullscreen
        self.updateState()

    def changeState(self, newState):
        platformutils.confirmMainThread()
        if newState == self.currentState:
            return
        self.currentState = newState
        self.updateState()
