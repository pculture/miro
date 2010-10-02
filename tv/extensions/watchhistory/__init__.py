import logging
import os
import time

my_logger = logging.getLogger('watchhistory')

from miro import app
from miro import api

WATCHER = None

class WatchHistory():
    def __init__(self):
        self.fp = None

        api.signals.system.connect('startup-success', self.handle_startup_success)
        api.signals.system.connect('shutdown', self.handle_shutdown)

    def handle_startup_success(self, obj):
        my_logger.info("startup")
        # open log file
        self.fp = open(os.path.join(api.get_support_directory(), "watched.log"), "a")

        # connect to will-play
        app.playback_manager.connect('selecting-file', self.handle_select_file)
        app.playback_manager.connect('will-play', self.handle_will_play)

    def handle_shutdown(self, obj):
        my_logger.info("shutdown")
        if self.fp:
            self.fp.close()

    def handle_select_file(self, obj, item_info):
        self.item_info = item_info

    def handle_will_play(self, obj, duration):
        self.fp.write(
            "%s: watched %s\n" % (time.ctime(), self.item_info.name))

def initialize():
    """Initializes the watchhistory module.
    """
    global WATCHER
    WATCHER = WatchHistory()
    my_logger.info("initialized")    
