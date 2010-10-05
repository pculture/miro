import logging
import os
import time
import csv

from miro import app
from miro import api

my_logger = logging.getLogger('watchhistory')

class WatchHistory():
    def __init__(self):
        self.csv_writer = None
        self.item_info = None
        api.signals.system.connect(
            'startup-success', self.handle_startup_success)

    def handle_startup_success(self, obj):
        my_logger.info("startup")
        # open log file
        logfile = os.path.join(api.get_support_directory(), "watched.csv")
        fp = open(logfile, "ab")
        self.csv_writer = csv.writer(fp)
        
        # connect to will-play
        app.playback_manager.connect('selecting-file', self.handle_select_file)
        app.playback_manager.connect('will-play', self.handle_will_play)

    def handle_select_file(self, obj, item_info):
        self.item_info = item_info

    def handle_will_play(self, obj, duration):
        if self.csv_writer and self.item_info:
            row = [
                time.ctime(),
                self.item_info.name,

                self.item_info.duration]
            self.csv_writer.writerow(row)
            # we wipe out self.item_info because will-play gets called
            # whenver someone starts watching an item (which we want
            # to log), but also whenever someone pauses and plays an
            # item (which we don't want to log)
            self.item_info = None
