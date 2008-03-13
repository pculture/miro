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
from threading import Lock
import time

from miro import app
from miro import util
from miro import config
from miro import prefs
from miro.download_utils import nextFreeFilename
from miro.frontends.html.displaybase import VideoDisplayBase
from miro.frontends.html.playbackcontroller import PlaybackControllerBase
from miro.platform import pyxpcomcalls

selectItemLock = Lock()

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally
        moviePath = ""
        try:
            moviePath = os.path.normpath(item.getVideoFilename())
            os.startfile(moviePath)
        except:
            print "DTV: movie %s could not be externally opened" % moviePath

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def initRenderers(self):
        app.renderers.append(VLCRenderer())

    def setRendererAndCallback(self, anItem, internal, external):
        #Always use VLC
        renderer = app.renderers[0]
        self.setExternal(False)
        self.selectItem(anItem, renderer)
        internal()

    def setArea(self, area):
        # we hardcode the videodisplay's area to be mainDisplayVideo
        pass
    def removedFromArea(self):
        # don't care about this either
        pass

    def goFullScreen(self):
        return app.vlcRenderer.goFullscreen(url)

    def exitFullScreen(self):
        return app.vlcRenderer.exitFullScreen(url)

    def setVolume(self, volume, moveSlider=True): 
        VideoDisplayBase.setVolume(self, volume)
        app.vlcRenderer.setVolume(self.volume)
        if moveSlider:
            app.jsBridge.positionVolumeSlider(self.volume)

    def fillMovieData (self, filename, movie_data, callback):
        print "fillMovieData (%s)" % (filename,)
#        dir = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
#        try:
#            os.makedirs(dir)
#        except:
#            pass
#        screenshot = os.path.join (dir, os.path.basename(filename) + ".png")

#        movie_data["screenshot"] = nextFreeFilename(screenshot)
        movie_data["screenshot"] = u""

        self.movie_data = movie_data
        self.callback = callback

#       Uncomment this to enable duration extraction

#         print "Calling renderer"
        app.vlcRenderer.extractMovieData (filename, movie_data["screenshot"]);
#         print "renderer returned"

    def extractFinish (self, duration, screenshot_success):
        print "extractFinish (%d, %s)" % (duration, screenshot_success)
        self.movie_data["duration"] = int (duration)
        if screenshot_success:
            self.movie_data["screenshot"] = u""
#            if self.movie_data["screenshot"] and not os.path.exists(self.movie_data["screenshot"]):
#                self.movie_data["screenshot"] = u""
        else:
            self.movie_data["screenshot"] = None
        self.callback()

# This is a major hack to avoid VLC crashes by giving it time to
# process each stop or play command. --NN
def lockAndPlay(func):
    def locked(*args, **kwargs):
        global selectItemLock
        selectItemLock.acquire()
        try:
            ret = func(*args, **kwargs)
            time.sleep(1)
            return ret
        finally:
            selectItemLock.release()
    return locked

class VLCRenderer:
    """The VLC renderer is very thin wrapper around the xine-renderer xpcom
    component. 
    """

    def canPlayFile(self, filename, callback):        
        logging.warn("VLCRenderer.canPlayfile() always returns True")
        callback(True)

    def selectItem(self, anItem):
        self.selectFile (anItem.getVideoFilename())

    @lockAndPlay
    def selectFile(self, filename):
        url = util.absolutePathToFileURL(filename)
        return app.vlcRenderer.selectURL(url)
    def setVolume(self, volume): 
        return app.vlcRenderer.setVolume(volume)
    @lockAndPlay
    def reset(self): 
        return app.vlcRenderer.reset()
    @lockAndPlay
    def play(self): 
        return app.vlcRenderer.play()
    def pause(self): 
        return app.vlcRenderer.pause()
    @lockAndPlay
    def stop(self): 
        return app.vlcRenderer.stop()
    def goToBeginningOfMovie(self): 
        return app.vlcRenderer.goToBeginningOfMovie()
    def getDuration(self, callback):
        c = pyxpcomcalls.XPCOMifyCallback(callback)
        app.vlcRenderer.getDuration(c)
    def getCurrentTime(self, callback):
        c = pyxpcomcalls.XPCOMifyCallback(callback)
        app.vlcRenderer.getCurrentTime(c)
    def setCurrentTime(self, seconds): 
        return app.vlcRenderer.setCurrentTime(float(seconds))
    @lockAndPlay
    def playFromTime(self, t):
        return app.vlcRenderer.playFromTime(float(t))
    def getRate(self, callback): 
        app.vlcRenderer.getRate(callback)
    def setRate(self, rate): 
        return app.vlcRenderer.setRate(rate)

    def movieDataProgramInfo(self, videoPath, thumbnailPath):
        # We don't use the app name here, so custom
        # named versions can use the same code --NN
        moviedata_util_filename = "Miro_MovieData.exe"
        cmdLine = [moviedata_util_filename, videoPath, thumbnailPath]
        env = os.environ.copy()
        currentPath = env.get("PATH")
        if currentPath is not None:
            currentPathSplit = currentPath.split(";")
        else:
            currentPathSplit = []
        currentPathSplit.insert(0, "xulrunner\\python")
        env['PATH'] = ';'.join(currentPathSplit)
        return cmdLine, env


###############################################################################
###############################################################################
