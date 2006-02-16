import gtk
import app

class MainWindowChanger(object):
    """Change which widgets are visible in the main window based on its
    current state.  The following states are possible:

    BROWSING -- Browsing a page with lots of feed links, like the
            Channel Guide.  Don't display any video controls.
    PLAYLIST -- Viewing a page with a video playlist.  Display the
        video controls, but only enable the play button.
    VIDEO -- Playing a video.  Display and enable all video controls.
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
    VIDEO_FULLSCREEN = 4
    VIDEO_ONLY_FULLSCREEN = 5

    def __init__(self, widgetTree, initialState):
        self.widgetTree = widgetTree
        self.currentState = None
        self.changeState(initialState)

    def updatePlayPauseButton(self):
        """Update the play/pause button to have the correct image."""
        playPauseImage = self.widgetTree['play-pause-image']
        if app.Controller.instance.videoDisplay.isPlaying:
            pixbuf = playPauseImage.render_icon(gtk.STOCK_MEDIA_PAUSE, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        else:
            pixbuf = playPauseImage.render_icon(gtk.STOCK_MEDIA_PLAY, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        playPauseImage.set_from_pixbuf(pixbuf)

    def updateFullscreenButton(self, windowIsFullscreen):
        fullscreenImage = self.widgetTree['fullscreen-image']
        if windowIsFullscreen:
            pixbuf = fullscreenImage.render_icon(gtk.STOCK_LEAVE_FULLSCREEN,
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        else:
            pixbuf = fullscreenImage.render_icon(gtk.STOCK_FULLSCREEN,
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        fullscreenImage.set_from_pixbuf(pixbuf)

    def setVideoWidgetsSensitive(self, sensitive):
        """Enable/disable widgets that only make sense to use when we're
        playing a video.
        """

        videoWidgets = ['save-video', 'play', 'stop', 'next-button',
                'previous-button', 'fullscreen-button']
        # delete-video should be in this list, but it's not implemented yet
        for widget in videoWidgets:
            self.widgetTree[widget].set_sensitive(sensitive)

    def changeState(self, newState):
        if newState == self.currentState:
            return
        if newState == self.BROWSING:
            self.widgetTree['video-control-box'].hide()
            self.widgetTree['fullscreen'].set_sensitive(False)
            self.widgetTree['leave-fullscreen'].set_sensitive(False)
            self.widgetTree['channels-box'].show()
            self.widgetTree['video-info-box'].hide()
            self.widgetTree['menubar'].show()
        elif newState == self.PLAYLIST:
            self.widgetTree['video-control-box'].hide()
            self.widgetTree['fullscreen'].set_sensitive(False)
            self.widgetTree['leave-fullscreen'].set_sensitive(False)
            self.widgetTree['channels-box'].show()
            self.widgetTree['video-info-box'].hide()
            self.widgetTree['menubar'].show()
            self.setVideoWidgetsSensitive(False)
        elif newState == self.VIDEO:
            self.widgetTree['video-control-box'].show()
            self.widgetTree['fullscreen'].set_sensitive(True)
            self.widgetTree['leave-fullscreen'].set_sensitive(False)
            self.widgetTree['channels-box'].show()
            self.widgetTree['video-info-box'].show()
            self.widgetTree['menubar'].show()
            self.setVideoWidgetsSensitive(True)
        elif newState == self.VIDEO_FULLSCREEN:
            self.widgetTree['video-control-box'].show()
            self.widgetTree['fullscreen'].set_sensitive(False)
            self.widgetTree['leave-fullscreen'].set_sensitive(True)
            self.widgetTree['channels-box'].hide()
            self.widgetTree['video-info-box'].show()
            self.widgetTree['menubar'].hide()
            self.setVideoWidgetsSensitive(True)
        elif newState == self.VIDEO_ONLY_FULLSCREEN:
            self.widgetTree['video-control-box'].hide()
            self.widgetTree['channels-box'].hide()
            self.widgetTree['video-info-box'].hide()
            self.widgetTree['menubar'].hide()
        else:
            raise TypeError("invalid state: %r" % newState)
        self.updatePlayPauseButton()
        self.currentState = newState
