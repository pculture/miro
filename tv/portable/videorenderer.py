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

"""videorenderer.py -- Base class for video renderers.  """

import util

class VideoRenderer:
    """VideoRenderer renderer base class."""
        
    def __init__(self):
        self.interactivelySeeking = False
    
    def canPlayItem(self, anItem):
        return self.canPlayFile (anItem.getVideoFilename())
    
    def canPlayFile(self, filename):
        return False

    def fillMovieData(self, filename, movie_data):
        return False
    
    def getDisplayTime(self):
        seconds = self.getCurrentTime()
        return util.formatTimeForUser(seconds)
        
    def getDisplayDuration(self):
        seconds = self.getDuration()
        return util.formatTimeForUser(seconds)

    def getDisplayRemainingTime(self):
        seconds = abs(self.getCurrentTime() - self.getDuration())
        return util.formatTimeForUser(seconds, -1)

    def getProgress(self):
        duration = self.getDuration()
        if duration == 0 or duration == None:
            return 0.0
        return self.getCurrentTime() / duration

    def setProgress(self, progress):
        if progress > 1.0:
            progress = 1.0
        if progress < 0.0:
            progress = 0.0
        self.setCurrentTime(self.getDuration() * progress)

    def selectItem(self, anItem):
        self.selectFile (anItem.getVideoFilename())

    def selectFile(self, filename):
        pass
        
    def reset(self):
        pass

    def setCurrentTime(self, seconds):
        pass

    def getDuration(self):
        return 0.0

    def setVolume(self, level):
        pass
                
    def goToBeginningOfMovie(self):
        pass

    def getCurrentTime(self):
        return None
        
    def playFromTime(self, position):
        self.play()
        self.setCurrentTime(position)
        
    def play(self):
        pass
        
    def pause(self):
        pass
        
    def stop(self):
        pass
    
    def getRate(self):
        return 1.0
    
    def setRate(self, rate):
        pass

    def movieDataProgramInfo(self, videoPath, thumbnailPath):
        raise NotImplementedError()
