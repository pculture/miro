# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""```workerprocess.py``` -- Miro worker subprocess

To avoid UI freezing due to the GIL, we farm out all CPU-intensive backend
tasks to this process.  See #17328 for more details.  Right now this just
includes feedparser, but we could pretty easily extend this to other tasks.
"""

import itertools

from miro import feedparserutil
from miro import moviedata
from miro import subprocessmanager
from miro import util

from miro.plat import utils

# define messages/handlers

class TaskMessage(subprocessmanager.SubprocessMessage):
    _id_counter = itertools.count()

    def __init__(self):
        subprocessmanager.SubprocessMessage.__init__(self)
        self.task_id = TaskMessage._id_counter.next()

class FeedparserTask(TaskMessage):
    def __init__(self, html):
        TaskMessage.__init__(self)
        self.html = html

class MediaMetadataExtractorTask(TaskMessage):
    def __init__(self, filename, thumbnail):
        TaskMessage.__init__(self)
        self.filename = filename
        self.thumbnail = thumbnail

class MovieDataProgramTask(TaskMessage):
    def __init__(self, source_path, screenshot_directory):
        TaskMessage.__init__(self)
        self.source_path = source_path
        self.screenshot_directory = screenshot_directory

class TaskResult(subprocessmanager.SubprocessResponse):
    def __init__(self, task_id, result):
        self.task_id = task_id
        self.result = result

class WorkerProcessHandler(subprocessmanager.SubprocessHandler):
    def call_handler(self, method, msg):
        try:
            # normally we send the result of our handler method back
            rv = method(msg)
        except StandardError, e:
            # if something breaks, we send the Exception back
            rv = e
        TaskResult(msg.task_id, rv).send_to_main_process()

    def handle_feedparser_task(self, msg):
        parsed_feed =  feedparserutil.parse(msg.html)
        # bozo_exception is sometimes C object that is not picklable.  We
        # don't use it anyways, so just unset the value
        parsed_feed['bozo_exception'] = None
        return parsed_feed

    def handle_media_metadata_extractor_task(self, msg):
        filename = msg.filename
        thumbnail = msg.thumbnail
        return utils.run_media_metadata_extractor(filename, thumbnail)

    def handle_movie_data_program_task(self, msg):
        return moviedata.process_file(msg.source_path,
                                      msg.screenshot_directory)

class WorkerProcessResponder(subprocessmanager.SubprocessResponder):
    def on_startup(self):
        _task_queue.run_pending_tasks()

    def handle_task_result(self, msg):
        _task_queue.process_result(msg)

# Manage task queue

class TaskQueue(object):
    def __init__(self):
        # maps task_ids to (msg, callback, errback) tuples
        self.tasks_in_progress = {}

    def reset(self):
        self.tasks_in_progress = {}

    def add_task(self, msg, callback, errback):
        """Add a new task to the queue."""
        self.tasks_in_progress[msg.task_id] = (msg, callback, errback)
        if _subprocess_manager.is_running:
            msg.send_to_process()

    def process_result(self, reply):
        """Process a TaskResult from our subprocess."""
        msg, callback, errback = self.tasks_in_progress.pop(reply.task_id)
        if isinstance(reply.result, Exception):
            errback(reply.result)
        else:
            callback(reply.result)

    def run_pending_tasks(self):
        """Rerun all tasks in the queue."""
        for msg, callback, errback in self.tasks_in_progress.values():
            msg.send_to_process()

_task_queue = TaskQueue()

# Manage subprocess
_subprocess_manager = subprocessmanager.SubprocessManager(TaskMessage,
        WorkerProcessResponder(), WorkerProcessHandler)

def startup():
    """Startup the worker process."""
    _subprocess_manager.start()

def shutdown():
    """Shutdown the worker process."""
    _subprocess_manager.shutdown()

# API for sending tasks
def send(msg, callback, errback):
    """Send a message to the worker process.

    :param msg: Message to send
    :param callback: function to call on success
    :param errback: function to call on error
    """
    _task_queue.add_task(msg, callback, errback)
