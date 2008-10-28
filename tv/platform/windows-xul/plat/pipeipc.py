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

"""pipeipc.py -- Create a windows named pipe to controll IPC between different
Miro processes.

The first proccess to start creates a named pipe, then a thread that listens
to that pipe.  Subsequent processes send a message over that pipe containing
command line arguments.  When the first process recieves a message from the
pipe, we try to open them using the singleclick module.
"""

import cPickle as pickle
import ctypes
from ctypes.wintypes import DWORD, HANDLE, ULONG
import os
import logging
import threading
from miro.plat import commandline

kernel32 = ctypes.windll.kernel32

ERROR_IO_PENDING = 997
ERROR_MORE_DATA = 234
ERROR_PIPE_CONNECTED = 535
ERROR_PIPE_LISTENING = 536
FILE_FLAG_OVERLAPPED = 0x40000000
INFINITE = 0xFFFF
INVALID_HANDLE_VALUE = -1
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_WAIT = 0x00000000

MIRO_IPC_PIPE_NAME = r'\\.\pipe\MiroIPC'


class PipeExists(Exception):
    """We tried to create a named pipe, but it already exists.  Probably a
    different Miro instance created it.
    """

class QuitThread(Exception):
    """Raised to exit out of the pipe listening thread."""

class PipeError(IOError):
    """An IO Error occurred on a pipe."""
    def __init__(self, description):
        str = "%s failed: %d" % (description, kernel32.GetLastError())
        IOError.__init__(self, str)

class _inner_struct(ctypes.Structure):
    _fields_ = [('Offset', DWORD),
                ('OffsetHigh', DWORD),
               ]

class _inner_union(ctypes.Union):
    _fields_  = [('anon_struct', _inner_struct), # struct
                 ('Pointer', ctypes.c_void_p),
                ]

class OVERLAPPED(ctypes.Structure):
    _fields_ = [('Internal', ctypes.POINTER(ULONG)),
                ('InternalHigh', ctypes.POINTER(ULONG)),
                ('union', _inner_union),
                ('hEvent', HANDLE),
               ]

class Server(object):
    def __init__(self):
        self.pipe = kernel32.CreateNamedPipeA(
                MIRO_IPC_PIPE_NAME, 
                PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                1, 51200, 51200, 100, None)
        if self.pipe == INVALID_HANDLE_VALUE:
            raise PipeExists()
        self.pipe_event = kernel32.CreateEventA(None, True, False, None)
        self.quit_event = kernel32.CreateEventA(None, True, False, None)
        self.event_array = (HANDLE * 2)(self.pipe_event, self.quit_event)
        self.overlapped = OVERLAPPED()
        self.overlapped.hEvent = self.pipe_event
        self.overlapped.Internal = None
        self.overlapped.InternalHigh = None
        self.overlapped.union.Pointer = None
        self.message_handler = MessageHandler()

    def start_process(self):
        self.thread = threading.Thread(target=self._thread)
        self.thread.start()

    def quit(self):
        kernel32.SetEvent(self.quit_event)

    def _wait_for_pipe(self):
        kernel32.WaitForMultipleObjects(2, self.event_array, False, INFINITE)
        if kernel32.WaitForSingleObject(self.quit_event, 0) == 0:
            raise QuitThread()

    def _process_overlap(self, length):
        return kernel32.GetOverlappedResult(self.pipe,
                self._overlapped_ref(), ctypes.byref(length), False)

    def _overlapped_ref(self):
        return ctypes.byref(self.overlapped)

    def _connect(self):
        rv = kernel32.ConnectNamedPipe(self.pipe, self._overlapped_ref())
        if not rv and kernel32.GetLastError() == ERROR_PIPE_CONNECTED:
            return
        if not rv and kernel32.GetLastError() == ERROR_IO_PENDING:
            self._wait_for_pipe()
        else:
            raise PipeError("ConnectNamedPipe")

    def _read_in(self):
        read_in = []
        c_length = DWORD()
        buffer = ctypes.create_string_buffer(1024)
        while True:
            rv = kernel32.ReadFile(self.pipe, buffer, 1023,
                    ctypes.byref(c_length), self._overlapped_ref())
            if not rv:
                if kernel32.GetLastError() == ERROR_IO_PENDING:
                    self._wait_for_pipe()
                elif kernel32.GetLastError() == ERROR_PIPE_LISTENING:
                    # Not sure why this happens, but it means we should just
                    # start at _connect()
                    return None
                elif kernel32.GetLastError() != ERROR_MORE_DATA:
                    raise PipeError("ReadFile")

            rv = self._process_overlap(c_length)

            buffer[c_length.value] = '\0'
            read_in.append(buffer.value)
            if rv:
                break
        return ''.join(read_in)

    def _write_out(self, data):
        c_length = DWORD()
        rv = kernel32.WriteFile(self.pipe, ctypes.create_string_buffer(data),
                len(data), ctypes.byref(c_length), self._overlapped_ref())
        if not rv and kernel32.GetLastError() == ERROR_IO_PENDING:
            self._wait_for_pipe()
            rv = self._process_overlap(c_length)
        if not rv: 
            raise PipeError("WriteFile")

    def _log_error(self, name):
        logging.warn("%s failed: %d" % (name, kernel32.GetLastError()))

    def _thread(self):
        while True:
            try:
                self._connect()
                data = self._read_in()
                if data is None:
                    continue
                self.message_handler.handle_message(data)
                self._write_out("OK")
                kernel32.DisconnectNamedPipe(self.pipe)
            except QuitThread:
                break
        logging.info("Pipe reader finished")

class MessageHandler(object):
    def handle_message(self, data):
        # import this stuff inside the function, so that import errors don't
        # mess with other code, which is part of the startup process
        from miro import app
        from miro import eventloop
        from miro import singleclick
        import gobject
        try:
            cmd_line = pickle.loads(data)
        except:
            logging.warn("Error unpickling message (%r)" % data)

        args = commandline.parse_command_line_string(cmd_line)
        eventloop.addIdle(singleclick.parse_command_line_args, 
                'parse command line', args=(args[1:],))
        gobject.idle_add(app.widgetapp.window._window.present)

def send_command_line_args():
    message = pickle.dumps(commandline.get_command_line_string())
    out_length = DWORD(0)
    out_buffer = ctypes.create_string_buffer(1024)
    kernel32.CallNamedPipeA(MIRO_IPC_PIPE_NAME,
            ctypes.create_string_buffer(message), len(message), out_buffer,
            1023, ctypes.byref(out_length), 20000)
