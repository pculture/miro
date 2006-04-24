# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Bram Cohen

import os
import sys
from bisect import insort
import socket
from cStringIO import StringIO
from traceback import print_exc
from errno import EWOULDBLOCK, ENOBUFS
from time import time, sleep
from BitTorrent import CRITICAL, FAQ_URL

try:
    from select import poll, error, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1000
except ImportError:
    from BitTorrent.selectpoll import poll, error, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1


all = POLLIN | POLLOUT


class SingleSocket(object):

    def __init__(self, raw_server, sock, handler, context, ip=None):
        self.raw_server = raw_server
        self.socket = sock
        self.handler = handler
        self.buffer = []
        self.last_hit = time()
        self.fileno = sock.fileno()
        self.connected = False
        self.context = context
        if ip is not None:
            self.ip = ip
        else:
            try:
                peername = self.socket.getpeername()
            except socket.error:
                self.ip = 'unknown'
            else:
                try:
                    self.ip = peername[0]
                except:
                    assert isinstance(peername, basestring)
                    self.ip = peername # UNIX socket, not really ip

    def close(self):
        sock = self.socket
        self.socket = None
        self.buffer = []
        del self.raw_server.single_sockets[self.fileno]
        self.raw_server.poll.unregister(sock)
        self.handler = None
        sock.close()

    def shutdown(self, val):
        self.socket.shutdown(val)

    def is_flushed(self):
        return len(self.buffer) == 0

    def write(self, s):
        assert self.socket is not None
        self.buffer.append(s)
        if len(self.buffer) == 1:
            self.try_write()

    def try_write(self):
        if self.connected:
            try:
                while self.buffer != []:
                    amount = self.socket.send(self.buffer[0])
                    if amount != len(self.buffer[0]):
                        if amount != 0:
                            self.buffer[0] = self.buffer[0][amount:]
                        break
                    del self.buffer[0]
            except socket.error, e:
                code, msg = e
                if code != EWOULDBLOCK:
                    self.raw_server.dead_from_write.append(self)
                    return
        if self.buffer == []:
            self.raw_server.poll.register(self.socket, POLLIN)
        else:
            self.raw_server.poll.register(self.socket, all)

def default_error_handler(x, y):
    print x


class RawServer(object):

    def __init__(self, doneflag, timeout_check_interval, timeout, noisy=True,
            errorfunc=default_error_handler, bindaddr='', tos=0):
        self.timeout_check_interval = timeout_check_interval
        self.timeout = timeout
        self.bindaddr = bindaddr
        self.tos = tos
        self.poll = poll()
        # {socket: SingleSocket}
        self.single_sockets = {}
        self.dead_from_write = []
        self.doneflag = doneflag
        self.noisy = noisy
        self.errorfunc = errorfunc
        self.funcs = []
        self.externally_added_tasks = []
        self.listening_handlers = {}
        self.serversockets = {}
        self.live_contexts = {None : True}
        self.add_task(self.scan_for_timeouts, timeout_check_interval)
        if sys.platform != 'win32':
            self.wakeupfds = os.pipe()
            self.poll.register(self.wakeupfds[0], POLLIN)
        else:
            # Windows doesn't support pipes with select(). Just prevent sleeps
            # longer than a second instead of proper wakeup for now.
            self.wakeupfds = (None, None)
            def wakeup():
                self.add_task(wakeup, 1)
            wakeup()

    def add_context(self, context):
        self.live_contexts[context] = True

    def remove_context(self, context):
        del self.live_contexts[context]
        self.funcs = [x for x in self.funcs if x[2] != context]

    def add_task(self, func, delay, context=None):
        if context in self.live_contexts:
            insort(self.funcs, (time() + delay, func, context))

    def external_add_task(self, func, delay, context=None):
        self.externally_added_tasks.append((func, delay, context))
        # Wake up the RawServer thread in case it's sleeping in poll()
        if self.wakeupfds[1] is not None:
            os.write(self.wakeupfds[1], 'X')

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        t = time() - self.timeout
        tokill = []
        for s in self.single_sockets.values():
            if s.last_hit < t:
                tokill.append(s)
        for k in tokill:
            if k.socket is not None:
                self._close_socket(k)

    def create_serversocket(port, bind='', reuse=False, tos=0):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if reuse and os.name != 'nt':
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.setblocking(0)
        if tos != 0:
            try:
                server.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
            except:
                pass
        server.bind((bind, port))
        server.listen(5)
        return server
    create_serversocket = staticmethod(create_serversocket)

    def start_listening(self, serversocket, handler, context=None):
        self.listening_handlers[serversocket.fileno()] = (handler, context)
        self.serversockets[serversocket.fileno()] = serversocket
        self.poll.register(serversocket, POLLIN)

    def stop_listening(self, serversocket):
        del self.listening_handlers[serversocket.fileno()]
        del self.serversockets[serversocket.fileno()]
        self.poll.unregister(serversocket)

    def start_connection(self, dns, handler=None, context=None, do_bind=True):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(0)
        if do_bind and self.bindaddr:
            sock.bind((self.bindaddr, 0))
        if self.tos != 0:
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, self.tos)
            except:
                pass
        try:
            sock.connect_ex(dns)
        except socket.error:
            sock.close()
            raise
        except Exception, e:
            sock.close()
            raise socket.error(str(e))
        self.poll.register(sock, POLLIN)
        s = SingleSocket(self, sock, handler, context, dns[0])
        self.single_sockets[sock.fileno()] = s
        return s

    def wrap_socket(self, sock, handler, context=None, ip=None):
        sock.setblocking(0)
        self.poll.register(sock, POLLIN)
        s = SingleSocket(self, sock, handler, context, ip)
        self.single_sockets[sock.fileno()] = s
        return s

    def _handle_events(self, events):
        for sock, event in events:
            if sock in self.serversockets:
                s = self.serversockets[sock]
                if event & (POLLHUP | POLLERR) != 0:
                    self.poll.unregister(s)
                    s.close()
                    self.errorfunc(CRITICAL, 'lost server socket')
                else:
                    try:
                        handler, context = self.listening_handlers[sock]
                        newsock, addr = s.accept()
                        newsock.setblocking(0)
                        nss = SingleSocket(self, newsock, handler, context)
                        self.single_sockets[newsock.fileno()] = nss
                        self.poll.register(newsock, POLLIN)
                        self._make_wrapped_call(handler. \
                           external_connection_made, (nss,), context=context)
                    except socket.error:
                        sleep(1)
            else:
                s = self.single_sockets.get(sock)
                if s is None:
                    if sock == self.wakeupfds[0]:
                        # Another thread wrote this just to wake us up.
                        os.read(sock, 1)
                    continue
                s.connected = True
                if event & POLLERR:
                    self._close_socket(s)
                    continue
                if event & (POLLIN | POLLHUP):
                    s.last_hit = time()
                    try:
                        data = s.socket.recv(100000)
                    except socket.error, e:
                        code, msg = e
                        if code != EWOULDBLOCK:
                            self._close_socket(s)
                        continue
                    if data == '':
                        self._close_socket(s)
                    else:
                        self._make_wrapped_call(s.handler.data_came_in,
                                                (s, data), s)
                # data_came_in could have closed the socket (s.socket = None)
                if event & POLLOUT and s.socket is not None:
                    s.try_write()
                    if s.is_flushed():
                        self._make_wrapped_call(s.handler.connection_flushed,
                                                (s,), s)

    def _pop_externally_added(self):
        while self.externally_added_tasks:
            task = self.externally_added_tasks.pop(0)
            self.add_task(*task)

    def listen_forever(self):
        while not self.doneflag.isSet():
            try:
                self._pop_externally_added()
                if len(self.funcs) == 0:
                    period = 1e9
                else:
                    period = self.funcs[0][0] - time()
                if period < 0:
                    period = 0
                events = self.poll.poll(period * timemult)
                if self.doneflag.isSet():
                    return
                while len(self.funcs) > 0 and self.funcs[0][0] <= time():
                    garbage, func, context = self.funcs.pop(0)
                    self._make_wrapped_call(func, (), context=context)
                self._close_dead()
                self._handle_events(events)
                if self.doneflag.isSet():
                    return
                self._close_dead()
            except error, e:
                if self.doneflag.isSet():
                    return
                # I can't find a coherent explanation for what the behavior
                # should be here, and people report conflicting behavior,
                # so I'll just try all the possibilities
                try:
                    code, msg, desc = e
                except:
                    try:
                        code, msg = e
                    except:
                        code = ENOBUFS
                if code == ENOBUFS:
                    self.errorfunc(CRITICAL, "Have to exit due to the TCP "
                                   "stack flaking out. "
                                   "Please see the FAQ at %s"%FAQ_URL)
                    return
            except KeyboardInterrupt:
                print_exc()
                return
            except:
                data = StringIO()
                print_exc(file=data)
                self.errorfunc(CRITICAL, data.getvalue())

    def _make_wrapped_call(self, function, args, socket=None, context=None):
        try:
            function(*args)
        except KeyboardInterrupt:
            raise
        except Exception, e:         # hopefully nothing raises strings
            # Incoming sockets can be assigned to a particular torrent during
            # a data_came_in call, and it's possible (though not likely) that
            # there could be a torrent-specific exception during the same call.
            # Therefore read the context after the call.
            if socket is not None:
                context = socket.context
            if self.noisy and context is None:
                data = StringIO()
                print_exc(file=data)
                self.errorfunc(CRITICAL, data.getvalue())
            if context is not None:
                context.got_exception(e)

    def _close_dead(self):
        while len(self.dead_from_write) > 0:
            old = self.dead_from_write
            self.dead_from_write = []
            for s in old:
                if s.socket is not None:
                    self._close_socket(s)

    def _close_socket(self, s):
        sock = s.socket.fileno()
        s.socket.close()
        self.poll.unregister(sock)
        del self.single_sockets[sock]
        s.socket = None
        self._make_wrapped_call(s.handler.connection_lost, (s,), s)
        s.handler = None
