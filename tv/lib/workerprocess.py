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

from collections import deque
import itertools
import logging
import threading

from miro import feedparserutil
from miro import filetags
from miro import messagetools
from miro import moviedata
from miro import subprocessmanager
from miro import util

from miro.plat import utils

# define messages/handlers

class WorkerMessage(subprocessmanager.SubprocessMessage):
    pass

class WorkerStartupInfo(WorkerMessage):
    def __init__(self, thread_count):
        self.thread_count = thread_count

class TaskMessage(WorkerMessage):
    _id_counter = itertools.count()
    priority = 0

    def __init__(self):
        subprocessmanager.SubprocessMessage.__init__(self)
        self.task_id = TaskMessage._id_counter.next()

class FeedparserTask(TaskMessage):
    priority = 20
    def __init__(self, html):
        TaskMessage.__init__(self)
        self.html = html

class MediaMetadataExtractorTask(TaskMessage):
    def __init__(self, filename, thumbnail):
        TaskMessage.__init__(self)
        self.filename = filename
        self.thumbnail = thumbnail

class MovieDataProgramTask(TaskMessage):
    priority = 10
    def __init__(self, source_path, screenshot_directory):
        TaskMessage.__init__(self)
        self.source_path = source_path
        self.screenshot_directory = screenshot_directory

class MutagenTask(TaskMessage):
    priority = 10
    def __init__(self, source_path, cover_art_directory):
        TaskMessage.__init__(self)
        self.source_path = source_path
        self.cover_art_directory = cover_art_directory

class CancelFileOperations(TaskMessage):
    """Cancel mutagen/movie data tasks for a set of path."""
    priority = 0
    def __init__(self, paths):
        TaskMessage.__init__(self)
        self.paths = paths

class WorkerProcessReady(subprocessmanager.SubprocessResponse):
    pass

class TaskResult(subprocessmanager.SubprocessResponse):
    def __init__(self, task_id, result):
        self.task_id = task_id
        self.result = result

class WorkerProcessHandler(subprocessmanager.SubprocessHandler):
    def __init__(self):
        subprocessmanager.SubprocessHandler.__init__(self)
        self.threads = []
        self.task_queue = WorkerTaskQueue()

    def call_handler(self, method, msg):
        try:
            if isinstance(msg, CancelFileOperations):
                # handle this message as soon as we can.
                handle_task(method, msg)
            elif isinstance(msg, TaskMessage):
                self.task_queue.add_task(method, msg)
            else:
                method(msg)
        except StandardError:
            subprocessmanager.send_subprocess_error_for_exception()

    def on_shutdown(self):
        self.task_queue.shutdown()

    def handle_worker_startup_info(self, msg):
        for i in xrange(msg.thread_count):
            t = threading.Thread(target=worker_thread, args=(self.task_queue,))
            t.daemon = True
            t.start()
            self.threads.append(t)
        WorkerProcessReady().send_to_main_process()

    def handle_cancel_file_operations(self, msg):
        self.task_queue.cancel_file_operations(msg.paths)
        return None

    # NOTE: all of the handle_*_task() methods below get called in one of our
    # worker threads, so they should only call thread-safe functions

    def handle_feedparser_task(self, msg):
        parsed_feed = feedparserutil.parse(msg.html)
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

    def handle_mutagen_task(self, msg):
        return filetags.process_file(msg.source_path, msg.cover_art_directory)

class _SinglePriorityQueue(object):
    """Manages tasks at a single priority for WorkerTaskQueue

    For any given priority we want to do the following:
        - If there is more than one TaskMessage class with that priority, we
          want to alternate handling tasks between them.
        - For a given TaskMessage class, we want to handle tasks FIFO.
    """
    def __init__(self, priority):
        self.priority = priority
        # map message classes to FIFO deques for that class
        self.fifo_map = {}
        # set up our structure for each task with our priority
        for cls in util.all_subclasses(TaskMessage):
            if cls.priority == priority:
                self.fifo_map[cls] = deque()
        # fifo_cycler is used to cycle through each fifo
        self.fifo_cycler = itertools.cycle(self.fifo_map.values())
        self.fifo_count = len(self.fifo_map)

    def add_task(self, handler_method, msg):
        self.fifo_map[msg.__class__].append((handler_method, msg))

    def get_next_task(self):
        for i, fifo in enumerate(self.fifo_cycler):
            if i >= self.fifo_count:
                # no tasks in any of our fifos
                return None
            if fifo:
                return fifo.popleft()

    def filter_messages(self, filterfunc, message_class):
        """Remove messages from the queue

        :param filterfunc: function to determine if messages should stay
        :param message_class: type of messages to filter
        """
        fifo = self.fifo_map[message_class]
        new_items = tuple((method, msg) for (method, msg) in fifo
                         if filterfunc(msg))
        fifo.clear()
        fifo.extend(new_items)

class WorkerTaskQueue(object):
    """Store the pending tasks for the worker process.

    WorkerTaskQueue is responsible for storing task info for each pending
    task, and getting the next one in order of priority.

    It's shared between the main subprocess thread, and all worker threads, so
    all methods need to be thread-safe.
    """
    def __init__(self):
        self.should_quit = False
        self.condition = threading.Condition()
        # queues_by_priority contains a _SinglePriorityQueue for each priority
        # level, ordered from highest to lowest priority
        self.queues_by_priority = []
        # queue_map maps priority levels to queues
        self.queue_map = {}
        self._init_queues()

    def _init_queues(self):
        all_prorities = set(cls.priority for
                            cls in util.all_subclasses(TaskMessage))
        for priority in sorted(all_prorities, reverse=True):
            queue = _SinglePriorityQueue(priority)
            self.queues_by_priority.append(queue)
            self.queue_map[queue.priority] = queue

    def add_task(self, handler_method, msg):
        """Add a new task to the queue.  """
        with self.condition:
            self.queue_map[msg.priority].add_task(handler_method, msg)
            self.condition.notify()

    def get_next_task(self):
        """Get the next task to be processed from the queue.

        This method will block if there are no tasks ready in the queue.

        It will return the tuple (handler_method, message) once there is
        something ready.  The worker thread should call
        handler_method(message) to run the task, and send back the result to
        the main process.

        get_next_task() returns None if the worker thread should quit.
        """
        with self.condition:
            if self.should_quit:
                return None
            next_task_info = self._get_next_task()
            if next_task_info is not None:
                return next_task_info
            # no tasks yet, need to wait for more
            self.condition.wait()
            if self.should_quit:
                return None
            return self._get_next_task()

    def _get_next_task(self):
        for queue in self.queues_by_priority:
            next_for_queue = queue.get_next_task()
            if next_for_queue is not None:
                return next_for_queue
        # no tasks in any of our queues
        return None

    def cancel_file_operations(self, paths):
        """Cancels all mutagen/movie data tasks for a list of paths."""
        # Acquire our lock as soon as possible.  We want to prevent other
        # tasks from getting tasks, since they may be about to deleted.
        with self.condition:
            path_set = set(paths)
            def filter_func(msg):
                return msg.source_path not in path_set
            for cls in (MutagenTask, MovieDataProgramTask):
                queue = self.queue_map[cls.priority]
                queue.filter_messages(filter_func, cls)

    def shutdown(self):
        # should be save to set this without the lock, since it's a boolean
        with self.condition:
            self.should_quit = True
            self.condition.notify_all()

def handle_task(handler_method, msg):
    """Process a TaskMessage."""
    try:
        # normally we send the result of our handler method back
        rv = handler_method(msg)
    except StandardError, e:
        # if something breaks, we send the Exception back
        rv = e
    TaskResult(msg.task_id, rv).send_to_main_process()

def worker_thread(task_queue):
    """Thread loop in the worker process."""

    while True:
        next_task = task_queue.get_next_task()
        if next_task is None:
            break
        handle_task(*next_task)

class WorkerProcessResponder(subprocessmanager.SubprocessResponder):
    def __init__(self):
        subprocessmanager.SubprocessResponder.__init__(self)
        self.worker_ready = False
        self.startup_message = None

    def on_startup(self):
        self.startup_message.send_to_process()
        _miro_task_queue.run_pending_tasks()

    def on_shutdown(self):
        self.worker_ready = False

    def on_restart(self):
        self.worker_ready = False

    def handle_task_result(self, msg):
        _miro_task_queue.process_result(msg)

    def handle_worker_process_ready(self, msg):
        self.worker_ready = True

class MiroTaskQueue(object):
    """Store the pending tasks for the main process.

    Responsible for:
        - Storing callbacks/errbacks for each pending task
        - Calling the callback/errback for a finished task
    """
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
            errback(msg, reply.result)
        else:
            callback(msg, reply.result)

    def run_pending_tasks(self):
        """Rerun all tasks in the queue."""
        for msg, callback, errback in self.tasks_in_progress.values():
            msg.send_to_process()

_miro_task_queue = MiroTaskQueue()

# Manage subprocess
_subprocess_manager = subprocessmanager.SubprocessManager(WorkerMessage,
        WorkerProcessResponder(), WorkerProcessHandler)

def startup(thread_count=3):
    """Startup the worker process."""

    startup_msg = WorkerStartupInfo(thread_count)
    _subprocess_manager.responder.startup_message = startup_msg
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
    _miro_task_queue.add_task(msg, callback, errback)

def cancel_tasks_for_files(paths):
    """Cancel mutagen and movie data tasks for a list of paths."""
    msg = CancelFileOperations(paths)
    # we don't care about the return value, but we still want to use the task
    # queue to queue up this message.
    def null_callback(msg, result):
        pass
    send(msg, null_callback, null_callback)
