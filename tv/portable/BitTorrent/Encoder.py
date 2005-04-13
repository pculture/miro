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

from socket import error as socketerror

from BitTorrent.Connecter import Connection
from BitTorrent import BTFailure


# header, reserved, download id, my id, [length, message]


class Encoder(object):

    def __init__(self, make_upload, downloader, choker, numpieces, ratelimiter,
               raw_server, config, my_id, schedulefunc, download_id, context):
        self.make_upload = make_upload
        self.downloader = downloader
        self.choker = choker
        self.numpieces = numpieces
        self.ratelimiter = ratelimiter
        self.raw_server = raw_server
        self.my_id = my_id
        self.config = config
        self.schedulefunc = schedulefunc
        self.download_id = download_id
        self.context = context
        self.everinc = False
        self.connections = {}
        self.complete_connections = {}
        self.spares = []
        self.banned = {}
        schedulefunc(self.send_keepalives, config['keepalive_interval'])

    def send_keepalives(self):
        self.schedulefunc(self.send_keepalives,
                          self.config['keepalive_interval'])
        for c in self.complete_connections:
            c.send_keepalive()

    def start_connection(self, dns, id):
        if dns[0] in self.banned:
            return
        if id == self.my_id:
            return
        for v in self.connections.values():
            if id and v.id == id:
                return
            if self.config['one_connection_per_ip'] and v.ip == dns[0]:
                return
        if len(self.connections) >= self.config['max_initiate']:
            if len(self.spares) < self.config['max_initiate'] and \
                   dns not in self.spares:
                self.spares.append(dns)
            return
        try:
            c = self.raw_server.start_connection(dns, None, self.context)
        except socketerror:
            pass
        else:
            con = Connection(self, c, id, True)
            self.connections[c] = con
            c.handler = con

    def connection_completed(self, c):
        self.complete_connections[c] = 1
        c.upload = self.make_upload(c)
        c.download = self.downloader.make_download(c)
        self.choker.connection_made(c)

    def ever_got_incoming(self):
        return self.everinc

    def how_many_connections(self):
        return len(self.complete_connections)

    def replace_connection(self):
        while len(self.connections) < self.config['max_initiate'] and \
                  self.spares:
            self.start_connection(self.spares.pop(), None)

    def close_connections(self):
        for c in self.connections.itervalues():
            if not c.closed:
                c.connection.close()
                c.closed = True

    def singleport_connection(self, listener, con):
        if con.ip in self.banned:
            return
        m = self.config['max_allow_in']
        if m and len(self.connections) >= m:
            return
        self.connections[con.connection] = con
        del listener.connections[con.connection]
        con.encoder = self
        con.connection.context = self.context

    def ban(self, ip):
        self.banned[ip] = None


class SingleportListener(object):

    def __init__(self, rawserver):
        self.rawserver = rawserver
        self.port = 0
        self.ports = {}
        self.torrents = {}
        self.connections = {}
        self.download_id = None

    def _check_close(self, port):
        if not port or self.port == port or self.ports[port][1] > 0:
            return
        serversocket = self.ports[port][0]
        self.rawserver.stop_listening(serversocket)
        serversocket.close()
        del self.ports[port]

    def open_port(self, port, config):
        if port in self.ports:
            self.port = port
            return
        serversocket = self.rawserver.create_serversocket(
            port, config['bind'], reuse=True, tos=config['peer_socket_tos'])
        self.rawserver.start_listening(serversocket, self)
        oldport = self.port
        self.port = port
        self.ports[port] = [serversocket, 0]
        self._check_close(oldport)

    def get_port(self):
        if self.port:
            self.ports[self.port][1] += 1
        return self.port

    def release_port(self, port):
        self.ports[port][1] -= 1
        self._check_close(port)

    def close_sockets(self):
        for serversocket, _ in self.ports.itervalues():
            self.rawserver.stop_listening(serversocket)
            serversocket.close()

    def add_torrent(self, infohash, encoder):
        if infohash in self.torrents:
            raise BTFailure("Can't start two separate instances of the same "
                            "torrent")
        self.torrents[infohash] = encoder

    def remove_torrent(self, infohash):
        del self.torrents[infohash]

    def select_torrent(self, conn, infohash):
        if infohash not in self.torrents:
            return
        self.torrents[infohash].singleport_connection(self, conn)

    def external_connection_made(self, connection):
        con = Connection(self, connection, None, False)
        self.connections[connection] = con
        connection.handler = con

    def replace_connection(self):
        pass
