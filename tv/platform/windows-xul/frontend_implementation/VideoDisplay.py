import app
import frontend
import frontend_implementation
import os
import threading

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally
        moviePath = ""
        try:
            moviePath = os.path.normpath(item.getPath())
            os.startfile(moviePath)
        except:
            print "DTV: movie %s could not be externally opened" % moviePath

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (app.VideoDisplayBase, frontend.HTMLDisplay):
    "Video player shown in a MainFrame's right-hand pane."

    def __init__(self):
        print "VideoDisplay init"
        app.VideoDisplayBase.__init__(self)

	self.lock = threading.RLock()
        self.mutationOutput = None
        self.queue = []
        print "Display initialized"        

    def initRenderers(self):
        print "initRenderers"
        self.renderers.append(VLCPluginRenderer())

    def selectItem(self, item):
        print "VideoDisplay select item"
        self.itemPath = item.getFilename()
        app.VideoDisplayBase.selectItem(self, item)
 
    def play(self):
        print "VideoDisplay play"
        html = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:t="http://www.participatorypolitics.org/"
      xmlns:i18n="http://www.participatoryculture.org/i18n">
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8" />
</head>

<body>
<embed type="application/x-vlc-plugin"
         name="video1"
         autostart="1" loop="yes" style="position: absolute; top: 0px;bottom: 0px; left: 0px; right: 0px"
"""
        html += ' target="file:///'
        html += self.itemPath.replace("\\","/")
        html += '''" id="video1" />

</body>
</html>
'''
        frontend_implementation.HTMLDisplay.pendingDocuments[self.getEventCookie()] = ("text/html", html)

        app.VideoDisplayBase.play(self)

    def pause(self):
        print "VideoDisplay pause"
        app.VideoDisplayBase.pause(self)

    def stop(self):
        print "VideoDisplay stop"
        app.VideoDisplayBase.stop(self)
    
    def goFullScreen(self):
        print "VideoDisplay fullscreen"
        app.VideoDisplayBase.goFullScreen(self)

    def exitFullScreen(self):
        print "VideoDisplay exit fullscreen"
        app.VideoDisplayBase.exitFullScreen(self)

    def setVolume(self, level):
        print "VideoDisplay set volume"
        app.VideoDisplayBase.setVolume(self, level)

    def muteVolume(self):
        print "VideoDisplay mute volume"
        app.VideoDisplayBase.muteVolume(self)

    def restoreVolume(self):
        print "VideoDisplay restore volume"
        app.VideoDisplayBase.restoreVolume(self)

    def onSelected(self, frame):
        print "VideoDisplay on selected"
        app.VideoDisplayBase.onSelected(self, frame)

    def onDeselected(self, frame):
        print "VideoDisplay deselected"
        app.VideoDisplayBase.onDeselected(self, frame)

class VLCPluginRenderer (app.VideoRenderer):

    def __init__(self):
        app.VideoRenderer.__init__(self)
        print "Renderer initialized"

    def reset(self):
        print "Renderer reset"
    def canPlayItem(self, item):
        print "canPlayItem"
        return True

    def selectItem(self, item):
        print "Renderer select item"
        self.itemPath = item.getFilename()

    def play(self):
        print "Renderer play"

    def pause(self):
        print "Renderer pause"

    def stop(self):
        print "Renderer stop"

    def goToBeginningOfMovie(self):
        print "Renderer go to beginning"

    def getDuration(self):
        print "Renderer getDuration"
        return 0

    def getCurrentTime(self):
        print "Renderer getCurrentTime"
        return 0

    def setCurrentTime(self, time):
        print "Renderer Set current time"

    def getRate(self):
        print "Renderer get rate"
        return 0.0

    def setRate(self, rate):
        print "Renderer set rate"
        
    def setVolume(self, level):
        print "Renderer set volume"


###############################################################################
#### Playlist item base class                                              ####
###############################################################################

class PlaylistItem:
    "The record that makes up VideoDisplay playlists."

    def getTitle(self):
        """Return the title of this item as a string, for visual presentation
        to the user."""
        raise NotImplementedError

    def getPath(self):
        """Return the full path in the local filesystem to the video file
        to play."""
        raise NotImplementedError

    def getLength(self):
        """Return the length of this item in seconds as a real number. This
        is used only cosmetically, for telling the user the total length
        of the current playlist and so on."""
        raise NotImplementedError

    def onViewed(self):
        """Called by the frontend when a clip is at least partially watched
        by the user. To handle this event, for example by marking the
        item viewed in the database, override this method in a subclass."""
        raise NotImplementedError

###############################################################################
###############################################################################
