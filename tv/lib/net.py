# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""net.py -- Low-level Networking Code

The main class here is ConnectionHandler, which is a state-based socket
handling class.  It's used for communication with the downloader daemon via a
socket.

This class also defines the base Exception classes used by httpclient.

"""

import errno
import logging
import socket

from miro import eventloop
from miro import util
from miro import signals
from miro import trapcall
from miro.clock import clock
from miro.gtcache import gettext as _

SOCKET_READ_TIMEOUT = 60
SOCKET_INITIAL_READ_TIMEOUT = 30
SOCKET_CONNECT_TIMEOUT = 15

# socket.ssl is deprecated as of Python 2.6, so we use socket_ssl for
# pre Python 2.6 and ssl.wrap_socket for Python 2.6 and later.
try:
    import ssl
    ssl.wrap_socket
    def convert_to_ssl(sock):
        return ssl.wrap_socket(sock)
except (ImportError, AttributeError):
    def convert_to_ssl(sock):
        return socket.ssl(sock)

class NetworkError(Exception):
    """Base class for all errors that will be passed to errbacks from get_url
    and friends.  NetworkErrors can be display in 2 ways:

    getFriendlyDescription() -- short, newbie friendly description 
    getLongDescription() -- detailed description
    """

    def __init__(self, shortDescription, longDescription=None):
        if longDescription is None:
            longDescription = shortDescription
        self.friendlyDescription = _("Error: %(msg)s", {"msg": shortDescription})
        self.longDescription = longDescription

    def getFriendlyDescription(self):
        return self.friendlyDescription

    def getLongDescription(self):
        return self.longDescription

    def __str__(self):
        return "%s: %s -- %s" % (self.__class__,
                util.stringify(self.getFriendlyDescription()), 
                util.stringify(self.getLongDescription()))

class ConnectionError(NetworkError):
    def __init__(self, errorMessage):
        self.friendlyDescription = _("Can't connect")
        self.longDescription = _("Connection Error: %(msg)s",
                                 {"msg": util.unicodify(errorMessage)})

class SSLConnectionError(ConnectionError):
    def __init__(self):
        self.friendlyDescription = _("Can't connect")
        self.longDescription = _("SSL connection error")

class ConnectionTimeout(NetworkError):
    def __init__(self, host):
        NetworkError.__init__(self, _('Timeout'),
                _('Connection to %(host)s timed out', {"host": host}))

def trap_call(object, function, *args, **kwargs):
    """Convenience function do a trapcall.trap_call, where when is
    'While talking to the network'
    """
    return trapcall.time_trap_call("Calling %s on %s" % (function, object), function, *args, **kwargs)

class NetworkBuffer(object):
    """Responsible for storing incomming network data and doing some basic
    parsing of it.  I think this is about as fast as we can do things in pure
    python, someday we may want to make it C...
    """
    def __init__(self):
        self.chunks = []
        self.length = 0

    def addData(self, data):
        self.chunks.append(data)
        self.length += len(data)

    def _mergeChunks(self):
        self.chunks = [''.join(self.chunks)]

    def has_data(self):
        return self.length > 0

    def discard_data(self):
        self.chunks = []
        self.length = 0

    def read(self, size=None):
        """Read at most size bytes from the data that has been added to the
        buffer.  """

        self._mergeChunks()
        if size is not None:
            rv = self.chunks[0][:size]
            self.chunks[0] = self.chunks[0][len(rv):]
        else:
            rv = self.chunks[0]
            self.chunks = []
        self.length -= len(rv)
        return rv

    def readline(self):
        """Like a file readline, with several difference:  
        * If there isn't a full line ready to be read we return None.  
        * Doesn't include the trailing line separator.
        * Both "\r\n" and "\n" act as a line ender
        """

        self._mergeChunks()
        split = self.chunks[0].split("\n", 1)
        if len(split) == 2:
            self.chunks[0] = split[1]
            self.length = len(self.chunks[0])
            if split[0].endswith("\r"):
                return split[0][:-1]
            else:
                return split[0]
        else:
            return None

    def unread(self, data):
        """Put back read data.  This make is like the data was never read at
        all.
        """
        self.chunks.insert(0, data)
        self.length += len(data)

    def getValue(self):
        self._mergeChunks()
        return self.chunks[0]

class _Packet(object):
    """A packet of data for the AsyncSocket class
    """
    def __init__(self, data, callback=None):
        self.data = data
        self.callback = callback

class AsyncSocket(object):
    """Socket class that uses the eventloop module.
    """

    MEMORY_ERROR_LIMIT = 5

    def __init__(self, closeCallback=None):
        """Create an AsyncSocket.  If closeCallback is given, it will be
        called if we detect that the socket has been closed durring a
        read/write operation.  The arguments will be the AsyncSocket object
        and either socket.SHUT_RD or socket.SHUT_WR.
        """
        self.toSend = []
        self.to_send_length = 0
        self.readSize = 4096
        self.socket = None
        self.readCallback = None
        self.closeCallback = closeCallback
        self.readTimeout = None
        self.timedOut = False
        self.connectionErrback = None
        self.disable_read_timeout = False
        self.readSomeData = False
        self.name = ""
        self.lastClock = None
        self.memoryErrors = 0

    def __str__(self):
        if self.name:
            return "%s: %s" % (type(self).__name__, self.name)
        else:
            return "Unknown %s" % (type(self).__name__,)

    # The complication in the timeout code is because creating and
    # cancelling a timeout costs some memory (timeout is in memory
    # until it goes off, even if cancelled.)
    def startReadTimeout(self):
        if self.disable_read_timeout:
            return
        self.lastClock = clock()
        if self.readTimeout is not None:
            return
        self.readTimeout = eventloop.add_timeout(SOCKET_INITIAL_READ_TIMEOUT, self.onReadTimeout,
                "AsyncSocket.onReadTimeout")

    def stopReadTimeout(self):
        if self.readTimeout is not None:
            self.readTimeout.cancel()
            self.readTimeout = None

    def open_connection(self, host, port, callback, errback,
                        disable_read_timeout=None):
        """Open a connection.  On success, callback will be called with this
        object.
        """
        if disable_read_timeout is not None:
            self.disable_read_timeout = disable_read_timeout
        self.name = "Outgoing %s:%s" % (host, port)

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, e:
            trap_call(self, errback, ConnectionError(e[1]))
            return
        self.socket.setblocking(0)
        self.connectionErrback = errback
        def handleGetHostByNameException(e):
            trap_call(self, errback, ConnectionError(e[1] + " (host: %s)" % host))
        def onAddressLookup(address):
            if self.socket is None:
                # the connection was closed while we were calling gethostbyname
                return
            try:
                rv = self.socket.connect_ex((address, port))
            except socket.gaierror:
                trap_call(self, errback, ConnectionError('gaierror'))
                return
            if rv in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
                eventloop.add_write_callback(self.socket, onWriteReady)
                self.socketConnectTimeout = eventloop.add_timeout(
                        SOCKET_CONNECT_TIMEOUT, onWriteTimeout,
                        "socket connect timeout")
            else:
                try:
                    msg = errno.errorcode[rv]
                except KeyError:
                    msg = "Unknown connection error: %s" % rv
                trap_call(self, errback, ConnectionError(msg))
        def onWriteReady():
            eventloop.remove_write_callback(self.socket)
            self.socketConnectTimeout.cancel()
            rv = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if rv == 0:
                trap_call(self, callback, self)
            else:
                msg = errno.errorcode.get(rv, _('Unknown Error code'))
                trap_call(self, errback, ConnectionError(msg))
            self.connectionErrback = None
        def onWriteTimeout():
            eventloop.remove_write_callback(self.socket)
            trap_call(self, errback, ConnectionTimeout(host))
            self.connectionErrback = None
        eventloop.call_in_thread(onAddressLookup, handleGetHostByNameException,
                socket.gethostbyname, "getHostByName - %s" % host, host)

    def acceptConnection(self, host, port, callback, errback):
        def finishAccept():
            eventloop.remove_read_callback(self.socket)
            (self.socket, addr) = self.socket.accept()
            trap_call(self, callback, self)
            self.connectionErrback = None

        self.name = "Incoming %s:%s" % (host, port)
        self.connectionErrback = errback
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        (self.addr, self.port) = self.socket.getsockname()
        self.socket.listen(63)
        eventloop.add_read_callback(self.socket, finishAccept)

    def close_connection(self):
        if self.isOpen():
            eventloop.stop_handling_socket(self.socket)
            self.stopReadTimeout()
            self.socket.close()
            self.socket = None
            if self.connectionErrback is not None:
                error = NetworkError(_("Connection closed"))
                trap_call(self, self.connectionErrback, error)
                self.connectionErrback = None

    def isOpen(self):
        return self.socket is not None

    def send_data(self, data, callback=None):
        """Send data out to the socket when it becomes ready.
        
        NOTE: currently we have no way of detecting when the data gets sent
        out, or if errors happen.
        """

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.toSend.append(_Packet(data, callback))
        self.to_send_length += len(data)
        eventloop.add_write_callback(self.socket, self.onWriteReady)

    def startReading(self, readCallback):
        """Start reading from the socket.  When data becomes available it will
        be passed to readCallback.  If there is already a read callback, it
        will be replaced.
        """

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = readCallback
        eventloop.add_read_callback(self.socket, self.onReadReady)
        self.startReadTimeout()

    def stopReading(self):
        """Stop reading from the socket."""

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = None
        eventloop.remove_read_callback(self.socket)
        self.stopReadTimeout()

    def onReadTimeout(self):
        if self.readSomeData:
            timeout = SOCKET_READ_TIMEOUT
        else:
            timeout = SOCKET_INITIAL_READ_TIMEOUT

        if clock() < self.lastClock + timeout:
            self.readTimeout = eventloop.add_timeout(self.lastClock + timeout - clock(), self.onReadTimeout,
                "AsyncSocket.onReadTimeout")
        else:
            self.readTimeout = None
            self.timedOut = True
            self.handleEarlyClose('read')

    def handleSocketError(self, code, msg, operation):
        if code in (errno.EWOULDBLOCK, errno.EINTR):
            return

        if operation == "write":
            expectedErrors = (errno.EPIPE, errno.ECONNRESET)
        else:
            expectedErrors = (errno.ECONNREFUSED, errno.ECONNRESET)
        if code not in expectedErrors:
            logging.warning("WARNING, got unexpected error during %s", operation)
            logging.warning("%s: %s", errno.errorcode.get(code), msg)
        self.handleEarlyClose(operation)

    def onWriteReady(self):
        try:
            if len(self.toSend) > 0:
                sent = self.socket.send(self.toSend[0].data)
            else:
                sent = 0
        except socket.error, (code, msg):
            self.handleSocketError(code, msg, "write")
        else:
            self.handleSentData(sent)

    def handleSentData(self, sent):
        if len(self.toSend) > 0:
            self.toSend[0].data = self.toSend[0].data[sent:]
            if len(self.toSend[0].data) == 0:
                if self.toSend[0].callback:
                    self.toSend[0].callback()
                self.toSend = self.toSend[1:]
        self.to_send_length -= sent
        if len(self.toSend) == 0:
            eventloop.remove_write_callback(self.socket)

    def onReadReady(self):
        try:
            data = self.socket.recv(self.readSize)
        except socket.error, (code, msg):
            self.handleSocketError(code, msg, "read")
        except MemoryError:
            # This happens because of a windows bug in the socket code (see
            # #4373).  Let's hope that things clear themselves up next time we
            # read.
            self.memoryErrors += 1
            if self.memoryErrors > self.MEMORY_ERROR_LIMIT:
                logging.error("ERROR: Too many MemoryErrors on %s", self)
                self.handleEarlyClose('read')
            else:
                logging.warning("WARNING: Memory error while reading from %s", self)
        else:
            self.memoryErrors = 0
            self.handleReadData(data)

    def handleReadData(self, data):
        self.startReadTimeout()
        if data == '':
            if self.closeCallback:
                trap_call(self, self.closeCallback, self, socket.SHUT_RD)
        else:
            self.readSomeData = True
            trap_call(self, self.readCallback, data)

    def handleEarlyClose(self, operation):
        self.close_connection()
        if self.closeCallback:
            if operation == 'read':
                type = socket.SHUT_RD
            else:
                type = socket.SHUT_WR
            trap_call(self, self.closeCallback, self, type)

class AsyncSSLStream(AsyncSocket):
    def __init__(self, closeCallback=None):
        super(AsyncSSLStream, self).__init__(closeCallback)
        self.interruptedOperation = None

    def open_connection(self, host, port, callback, errback,
                        disable_read_timeout=None):
        def onSocketOpen(self):
            self.socket.setblocking(1)
            eventloop.call_in_thread(onSSLOpen, handleSSLError, convert_to_ssl,
                                   "AsyncSSL onSocketOpen()",
                                   self.socket)
        def onSSLOpen(ssl):
            if self.socket is None:
                # the connection was closed while we were calling
                # convert_to_ssl
                return
            self.socket.setblocking(0)
            self.ssl = ssl
            # finally we can call the actuall callback
            callback(self)
        def handleSSLError(error):
            logging.error("handleSSLError: %r", error)
            errback(SSLConnectionError())
        super(AsyncSSLStream, self).open_connection(host, port, onSocketOpen,
                errback, disable_read_timeout)

    def resumeNormalCallbacks(self):
        if self.readCallback is not None:
            eventloop.add_read_callback(self.socket, self.onReadReady)
        if len(self.toSend) != 0:
            eventloop.add_write_callback(self.socket, self.onWriteReady)

    def handleSocketError(self, code, msg, operation):
        if code in (socket.SSL_ERROR_WANT_READ, socket.SSL_ERROR_WANT_WRITE):
            if self.interruptedOperation is None:
                self.interruptedOperation = operation
            elif self.interruptedOperation != operation:
                signals.system.failed("When talking to the network", 
                details="socket error for the wrong SSL operation")
                self.close_connection()
                return
            eventloop.stop_handling_socket(self.socket)
            if code == socket.SSL_ERROR_WANT_READ:
                eventloop.add_read_callback(self.socket, self.onReadReady)
            else:
                eventloop.add_write_callback(self.socket, self.onWriteReady)
        elif code in (socket.SSL_ERROR_ZERO_RETURN, socket.SSL_ERROR_SSL,
                socket.SSL_ERROR_SYSCALL, socket.SSL_ERROR_EOF):
            self.handleEarlyClose(operation)
        else:
            super(AsyncSSLStream, self).handleSocketError(code, msg,
                    operation)

    def onWriteReady(self):
        if self.interruptedOperation == 'read':
            return self.onReadReady()
        try:
            if len(self.toSend) > 0:
                sent = self.ssl.write(self.toSend[0].data)
            else:
                sent = 0
        except socket.error, (code, msg):
            self.handleSocketError(code, msg, "write")
        else:
            if self.interruptedOperation == 'write':
                self.resumeNormalCallbacks()
                self.interruptedOperation = None
            self.handleSentData(sent)

    def onReadReady(self):
        if self.interruptedOperation == 'write':
            return self.onWriteReady()
        try:
            data = self.ssl.read(self.readSize)
        except socket.error, (code, msg):
            self.handleSocketError(code, msg, "read")
        else:
            if self.interruptedOperation == 'read':
                self.resumeNormalCallbacks()
                self.interruptedOperation = None
            self.handleReadData(data)

class ConnectionHandler(object):
    """Base class to handle asynchronous network streams.  It implements a
    simple state machine to deal with incomming data.

    Sending data: Use the send_data() method.

    Reading Data: Add entries to the state dictionary, which maps strings to
    methods.  The state methods will be called when there is data available,
    which can be read from the buffer variable.  The states dictionary can
    contain a None value, to signal that the handler isn't interested in
    reading at that point.  Use changeState() to switch states.

    Subclasses should override the handle_close() method to handle the
    socket closing.
    """
    stream_factory = AsyncSocket

    def __init__(self):
        self.buffer = NetworkBuffer()
        self.states = {'initializing': None, 'closed': None}
        self.stream = self.stream_factory(closeCallback=self.closeCallback)
        self.changeState('initializing')
        self.name = ""

    def __str__(self):
        return "%s -- %s" % (self.__class__, self.state)

    def open_connection(self, host, port, callback, errback,
                        disable_read_timeout=None):
        self.name = "Outgoing %s:%s" % (host, port)
        self.host = host
        self.port = port
        def callbackIntercept(asyncSocket):
            if callback:
                trap_call(self, callback, self)
        self.stream.open_connection(host, port, callbackIntercept, errback,
                                    disable_read_timeout)

    def close_connection(self):
        if self.stream.isOpen():
            self.stream.close_connection()
        self.changeState('closed')
        self.buffer.discard_data()

    def send_data(self, data, callback=None):
        self.stream.send_data(data, callback)

    def changeState(self, newState):
        self.readHandler = self.states[newState]
        self.state = newState
        self.updateReadCallback()

    def updateReadCallback(self):
        if self.readHandler is not None:
            self.stream.startReading(self.handleData)
        elif self.stream.isOpen():
            try:
                self.stream.stopReading()
            except KeyError:
                pass

    def handleData(self, data):
        self.buffer.addData(data)
        lastState = self.state
        self.readHandler()
        # If we switch states, continue processing the buffer.  There may be
        # extra data that the last read handler didn't read in
        while self.readHandler is not None and lastState != self.state:
            lastState = self.state
            self.readHandler()

    def closeCallback(self, stream, type):
        self.handle_close(type)

    def handle_close(self, type):
        """Handle our stream becoming closed.  Type is either socket.SHUT_RD,
        or socket.SHUT_WR.
        """
        raise NotImplementedError()
