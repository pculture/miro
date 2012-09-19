# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""threadcheck -- check that we are running in the right thread.
"""

import threading
import traceback

eventloop_thread = None
ui_thread = None

class ThreadError(StandardError):
    """Raised when we are running code in the wrong thread.
    """
    pass

def set_eventloop_thread(thread):
    global eventloop_thread
    eventloop_thread = thread

def set_ui_thread(thread):
    global ui_thread
    ui_thread = thread

def confirm_eventloop_thread():
    """Confirm that we are running in the eventloop thread.

    If we aren't then a ThreadError will be raised
    """
    _confirm_thread(eventloop_thread, 'Eventloop thread')

def confirm_ui_thread():
    """Confirm that we are running in the UI thread.

    If we aren't then a ThreadError will be raised
    """
    _confirm_thread(ui_thread, 'UI thread')

def _confirm_thread(correct_thread, thread_name):
    if correct_thread is None:
        raise ThreadError("%s not set" % thread_name)
    if correct_thread != threading.currentThread():
        raise ThreadError("Code running in %s instead of the %s" %
                          (threading.currentThread(), thread_name))
