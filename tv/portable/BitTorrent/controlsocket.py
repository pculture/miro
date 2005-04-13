# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written my Uoti Urpala

import os
import socket
import sys

from binascii import b2a_hex

from BitTorrent.RawServer import RawServer
from BitTorrent import BTFailure

def toint(s):
    return int(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) +
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))


class ControlsocketListener(object):

    def __init__(self, callback):
        self.callback = callback

    def external_connection_made(self, connection):
        connection.handler = MessageReceiver(self.callback)


class MessageReceiver(object):

    def __init__(self, callback):
        self.callback = callback
        self._buffer = []
        self._buffer_len = 0
        self._reader = self._read_messages()
        self._next_len = self._reader.next()

    def _read_messages(self):
        while True:
            yield 4
            l = toint(self._message)
            yield l
            action = self._message
            yield 4
            l = toint(self._message)
            yield l
            data = self._message
            self.callback(action, data)

    # copied from Connecter.py
    def data_came_in(self, conn, s):
        while True:
            i = self._next_len - self._buffer_len
            if i > len(s):
                self._buffer.append(s)
                self._buffer_len += len(s)
                return
            m = s[:i]
            if self._buffer_len > 0:
                self._buffer.append(m)
                m = ''.join(self._buffer)
                self._buffer = []
                self._buffer_len = 0
            s = s[i:]
            self._message = m
            try:
                self._next_len = self._reader.next()
            except StopIteration:
                self._reader = None
                conn.close()
                return

    def connection_lost(self, conn):
        self._reader = None
        pass

    def connection_flushed(self, conn):
        pass


class ControlSocket(object):

    def __init__(self, config):
        self.socket_filename = os.path.join(config['data_dir'], 'ui_socket')

    def set_rawserver(self, rawserver):
        self.rawserver = rawserver

    def start_listening(self, callback):
        self.rawserver.start_listening(self.controlsocket,
                                  ControlsocketListener(callback))

    def create_socket_inet(self):
        try:
            controlsocket = RawServer.create_serversocket(56881,
                                                   '127.0.0.1', reuse=True)
        except socket.error, e:
            raise BTFailure("Could not create control socket: "+str(e))
        self.controlsocket = controlsocket

    def send_command_inet(self, rawserver, action, data = ''):
        r = MessageReceiver(lambda action, data: None)
        try:
            conn = rawserver.start_connection(('127.0.0.1', 56881), r)
        except socket.error, e:
            raise BTFailure('Could not send command: ' + str(e))
        conn.write(tobinary(len(action)))
        conn.write(action)
        conn.write(tobinary(len(data)))
        conn.write(data)

    #blocking version without rawserver
    def send_command_inet(self, action, data=''):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(('127.0.0.1', 56881))
            s.send(tobinary(len(action)))
            s.send(action)
            s.send(tobinary(len(data)))
            s.send(data)
            s.close()
        except socket.error, e:
            s.close()
            raise BTFailure('Could not send command: ' + str(e))

    def create_socket_unix(self):
        filename = self.socket_filename
        if os.path.exists(filename):
            try:
                self.send_command_unix('no-op')
            except BTFailure:
                pass
            else:
                raise BTFailure("Could not create control socket: already in use")

            try:
                os.unlink(filename)
            except OSError, e:
                raise BTFailure("Could not remove old control socket filename:"
                                + str(e))
        try:
            controlsocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            controlsocket.setblocking(0)
            controlsocket.bind(filename)
            controlsocket.listen(5)
        except socket.error, e:
            raise BTFailure("Could not create control socket: "+str(e))
        self.controlsocket = controlsocket

    def send_command_unix(self, rawserver, action, data = ''):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        filename = self.socket_filename
        try:
            s.connect(filename)
        except socket.error, e:
            raise BTFailure('Could not send command: ' + str(e))
        r = MessageReceiver(lambda action, data: None)
        conn = rawserver.wrap_socket(s, r, ip = s.getpeername())
        conn.write(tobinary(len(action)))
        conn.write(action)
        conn.write(tobinary(len(data)))
        conn.write(data)

    # blocking version without rawserver
    def send_command_unix(self, action, data=''):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        filename = self.socket_filename
        try:
            s.connect(filename)
            s.send(tobinary(len(action)))
            s.send(action)
            s.send(tobinary(len(data)))
            s.send(data)
            s.close()
        except socket.error, e:
            s.close()
            raise BTFailure('Could not send command: ' + str(e))

    def close_socket(self):
        self.rawserver.stop_listening(self.controlsocket)
        self.controlsocket.close()

    if sys.platform != 'win32':
        send_command = send_command_unix
        create_socket = create_socket_unix
    else:
        send_command = send_command_inet
        create_socket = create_socket_inet
