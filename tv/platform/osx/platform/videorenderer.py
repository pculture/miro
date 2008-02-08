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

"""videorenderer.py -- Base class for video renderers.  """

from miro import util
import logging

class VideoRenderer:
    """VideoRenderer renderer base class."""
        
    def __init__(self):
        self.interactivelySeeking = False
    
    def fillMovieData(self, filename, movie_data):
        return False
    
    def getDisplayTime(self, callback = None):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayTime(). Please, update your code")
            return ""
        else:
            self.getCurrentTime(lambda secs : callback(util.formatTimeForUser(secs)))

    def getDisplayDuration(self, callback = None):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayDuration(). Please, update your code")
            return ""
        else:
            self.getDuration(lambda secs : callback(util.formatTimeForUser(secs)))

    def getDisplayRemainingTime(self, callback = None):
        def startCallbackChain():
            self.getDuration(durationCallback)
        def durationCallback(duration):
            self.getCurrentTime(lambda ct: currentTimeCallback(ct, duration))
        def currentTimeCallback(currentTime, duration):
            callback(util.formatTimeForUser(abs(currentTime-duration), -1))
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayRemainingTime(). Please, update your code")
            return ""
        else:
            startCallbackChain()

    def getProgress(self, callback = None):
        def startCallbackChain():
            self.getDuration(durationCallback)
        def durationCallback(duration):
            self.getCurrentTime(lambda ct: currentTimeCallback(ct, duration))
        def currentTimeCallback(currentTime, duration):
            if currentTime == 0 or duration == 0:
                callback(0.0)
            else:
                callback(currentTime / duration)
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getProgress(). Please, update your code")
            return 0.0
        else:
            startCallbackChain()

    def setProgress(self, progress):
        if progress > 1.0:
            progress = 1.0
        if progress < 0.0:
            progress = 0.0
        self.getDuration(lambda x: self.setCurrentTime(x*progress))

    def selectItem(self, anItem):
        self.selectFile (anItem.getVideoFilename())

    def selectFile(self, filename):
        pass
        
    def reset(self):
        pass

    def setCurrentTime(self, seconds):
        pass

    def getDuration(self, callback = None):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDuration(). Please, update your code")
            return 0.0
        else:
            callback(0.0)

    def setVolume(self, level):
        pass
                
    def goToBeginningOfMovie(self):
        pass

    def getCurrentTime(self, callback):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getCurrentTime(). Please, update your code")
            return None
        else:
            callback(None)
        
    def playFromTime(self, position):
        self.play()
        self.setCurrentTime(position)
        
    def play(self):
        pass
        
    def pause(self):
        pass
        
    def stop(self):
        pass
    
    def getRate(self, callback):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getRate(). Please, update your code")
            return 1.0
        else:
            callback(1.0)
    
    def setRate(self, rate):
        pass

    def movieDataProgramInfo(self, videoPath, thumbnailPath):
        raise NotImplementedError()
