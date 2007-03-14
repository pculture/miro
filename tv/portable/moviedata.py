from fasttypes import LinkedList
from eventloop import asIdle
import app

RUNNING_MAX = 3

class MovieDataUpdater:
    def __init__ (self):
        self.vital = LinkedList()
        self.runningCount = 0
        self.inShutdown = False

    def requestUpdate (self, item):
        if self.inShutdown:
            return
        if not item.getVideoFilename():
            return
        if item.downloader and not item.downloader.isFinished():
            return
        if self.runningCount < RUNNING_MAX:
            self.update(item)
        else:
            self.vital.prepend(item)

    @asIdle
    def updateFinished (self, item, movie_data):
        if item.idExists():
            item.duration = movie_data["duration"]
            item.screenshot = movie_data["screenshot"]
            item.updating_movie_info = False
            item.signalChange()

        self.runningCount -= 1

        if self.inShutdown:
            return

        while self.runningCount < RUNNING_MAX and len (self.vital) > 0:
            next = self.vital.pop()
            self.update (next)

    def update (self, item):
        if item.updating_movie_info:
            return
        item.updating_movie_info = True
        movie_data = {"duration": -1, "screenshot": ""}
        self.runningCount += 1
        app.controller.videoDisplay.fillMovieData (item.getVideoFilename(), movie_data, lambda: self.updateFinished (item, movie_data))

    @asIdle
    def shutdown (self):
        self.inShutdown = True

movieDataUpdater = MovieDataUpdater()
