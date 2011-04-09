# pydaap - a Python-based daap media sharing library
# Copyright (C) 2010 Participatory Culture Foundation
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

# libdaap.py
# Server/Client implementation of DAAP

import errno
import os
import sys
import itertools
import socket
import random
import traceback
# XXX merged into urllib.urlparse in Python 3
import urlparse
# XXX merged into http.server in Python 3.
import BaseHTTPServer
import SocketServer
import threading
import httplib

# Where do I get this guy in Python?
# NB: equivalent to INT32_MAX.
MAX_SESSION = 2147483647

import mdns
from const import *
from subr import (encode_response, decode_response, split_url_path, atoi,
                  atol, StreamObj, ChunkedStreamObj, find_daap_tag,
                  find_daap_listitems)

# Configurable options (or do via command line).
DEFAULT_PORT = 3689
DAAP_TIMEOUT = 1800    # timeout (in seconds)

DAAP_MAXCONN = 10      # Number of maximum connections we want to allow.

# !!! No user servicable parts below. !!!

VERSION = '0.1'

DAAP_VERSION_MAJOR = 3
DAAP_VERSION_MINOR = 0
DAAP_VERSION = ((DAAP_VERSION_MAJOR << 16)|DAAP_VERSION_MINOR)

DMAP_VERSION_MAJOR = 2
DMAP_VERSION_MINOR = 0
DMAP_VERSION = ((DMAP_VERSION_MAJOR << 16)|DMAP_VERSION_MINOR)

DAAP_OK = 200          # Also sent with mstt
DAAP_NOCONTENT = 204   # Acknowledged but no content to send back
DAAP_PARTIAL_CONTENT = 206 # Partial content, if Range header included.
DAAP_FORBIDDEN = 403   # Access denied
DAAP_BADREQUEST = 400  # Bad URI request
DAAP_FILENOTFOUND = 404 # File not found
DAAP_UNAVAILABLE = 503 # We are full

DEFAULT_CONTENT_TYPE = 'application/x-dmap-tagged'

DEFAULT_DAAP_META = ('dmap.itemkind,dmap.itemid,dmap.itemname,' + 
                     'dmap.containeritemid,dmap.parentcontainerid,' +
                     'daap.songtime,daap.songsize,daap.songformat,' +
                     'daap.songalbumartist,com.apple.itunes.mediakind')
DEFAULT_DAAP_PLAYLIST_META = ('dmap.itemid,dmap.itemname,dmap.persistentid,' +
                              'daap.baseplaylist,dmap.itemcount,' +
                              'dmap.parentcontainerid,dmap.persistentid')

class SessionObject(object):
    # Container object for a daap session.  Basically a heartbeat timeout
    # timer object and a generation counter so we can impose some ordering
    # on the requests which come in.
    pass

class DaapTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    # GRRR!  Stupid Windows!  When bind() is called twice on a socket
    # it should return EADDRINUSE on the second one - Windows doesn't!
    # Use robust=True (default) in make_daap_server() and it will pick 
    # a new port.
    # allow_reuse_address = True    # setsockopt(... SO_REUSEADDR, 1)
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass,
                 bind_and_activate=True):
        SocketServer.TCPServer.__init__(self, server_address,
                                        RequestHandlerClass,
                                        bind_and_activate)
        self.finished_callback = None
        self.session_lock = threading.Lock()
        self.debug = False
        self.log_message_callback = None

    # New functions in subclass.  Note: we can separate some of these out
    # into separate libraries but not now.
    def set_backend(self, backend):
        self.backend = backend

    def set_finished_callback(self, callback):
        self.finished_callback = callback

    def set_log_message_callback(self, callback):
        self.log_message_callback = callback

    def set_debug(self, debug):
        self.debug = debug

    def set_name(self, name):
        self.name = name

    def set_maxconn(self, maxconn):
        self.maxconn = maxconn
        self.activeconn = dict()

    def daap_timeout_callback(self, s):
        self.del_session(s)
        self.finished_callback(s)

    def session_count(self):
        return len(self.activeconn)

    def new_session(self):
        with self.session_lock:
            if self.session_count() == self.maxconn:
                return None
            while True:
                # NB: the session must be a non-zero.
                s = random.randint(1, MAX_SESSION)
                if not s in self.activeconn:
                    break
            session_obj = SessionObject()
            self.activeconn[s] = session_obj
            session_obj.timer = threading.Timer(DAAP_TIMEOUT,
                                                self.daap_timeout_callback,
                                                [s])
            session_obj.counter = itertools.count()
            current_thread = threading.current_thread()
            current_thread.generation = session_obj.counter.next()
            self.activeconn[s].timer.start()
        return s

    def renew_session(self, s):
        with self.session_lock:
            try:
                self.activeconn[s].timer.cancel()
            except KeyError:
                return False
            # Pants...  we need to create a new timer object.
            self.activeconn[s].timer = threading.Timer(DAAP_TIMEOUT,
                                                   self.daap_timeout_callback,
                                                   [s])
            current_thread = threading.current_thread()
            current_thread.generation = self.activeconn[s].counter.next()
            self.activeconn[s].timer.start()
            # OK, thank the caller for telling us the guy's alive
            return True

    def handle_error(self, request, client_address):
        pass

    def del_session(self, s):
        # maybe the guy tried to trick us by running /logout with no active
        # conn.
        with self.session_lock:
            try:
                self.activeconn[s].timer.cancel()
                # XXX can't just delete? - need to keep a reference count 
                # for the connection, we can have data/control connection?
                del self.activeconn[s]
            except KeyError:
                pass

class DaapHttpRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'daap.py' + ' ' + VERSION

    # Not used at the moment.
    # def __init__(self, request, client_address, server):
    #    super(BaseHTTPRequestHandler, self).__init__(self, request,
    #                                                   client_address,
    #                                                   server)
    def log_message(self, format, *args):
        if self.server.log_message_callback:
            self.server.log_message_callback(format, *args)

    def finish(self):
        try:
            self.server.del_session(self.session)
            if self.server.finished_callback:
                self.server.finished_callback(self.session)
            self.log_message('finish called on session %d.  Bye ...',
                             self.session)
        except AttributeError:
            pass
        # XXX Lousy python module.
        # super(DaapHttpRequestHandler, self).finish()
        try:
            BaseHTTPServer.BaseHTTPRequestHandler.finish(self)
        except IOError:
            # Silence broken pipe error.
            pass

    def do_send_reply(self, rcode, reply, content_type=DEFAULT_CONTENT_TYPE,
                      extra_headers=[]):
        blob = encode_response(reply)
        try:
            self.send_response(rcode)
            self.send_header('Content-type', content_type)
            self.send_header('Daap-Server', self.server_version)
            self.send_header('Content-length', str(len(blob)))
            # Note: we currently do not have the ability to replace or 
            # Note: we currently do not have the ability to replace or 
            # override the default headers.
            for k, v in extra_headers:
                self.send_header(k, v)
            for k, v in blob.get_headers():
                self.send_header(k, v)
            self.end_headers()
            for chunk in blob:
                self.wfile.write(chunk)
        # Remote guy could be mean and cut us off.  If so, silence the broken
        # pipe error, and continue on our merry way
        except IOError:
            session = getattr(self, 'session', 0)
            if session:
                self.server.del_session(session)
            raise    # Give upper layer a chance to deal

    # Convenience function: convenient that session-id must be non-zero so
    # you can use it for True/False testing too.
    def get_session(self):
        path, query = split_url_path(self.path)
        session = 0
        if not query or not 'session-id' in query.keys():
            pass
        else:
            try:
                session = int(query['session-id'])
                if not self.server.renew_session(session):
                    session = 0
            except ValueError:
                pass
        return session

    def do_server_info(self):
        reply = []
        # Append standard codes
        reply.append(('mstt', DAAP_OK))   # OK
        reply.append(('apro', DAAP_VERSION))
        reply.append(('mpro', DMAP_VERSION))
        reply.append(('minm', self.server_version))    # XXX FIXME
        reply.append(('mstm', DAAP_TIMEOUT))

        # 'msup' not supported, but we don't indicate that by writing a 0.
        # We do it by leaving it out.
        not_supported = [
                         'msix',    # Indexing
                         'msex',    # Extensions
                         'msau',    # password?
                         'msqy',    # queries
                         'msrs',    # resolve
                         'msbr',    # browsing
                         'mspi',    # persistent ids
                        ]
        supported = [
                     'msal',        # auto-logout
                     'mslr'         # login
                    ]
        for code in not_supported:
            reply.append((code, 0))
        for code in supported:
            reply.append((code, 1))

        reply.append(('msdc', 1))   # database count

        # Wrap this around a msrv (server info) response
        reply = [('msrv', reply)]
        # Bye bye, butterfly ...
        return (DAAP_OK, reply, [])

    def do_content_codes(self):
        reply = []
        # build the content codes
        content_codes = []
        for k in dmap_consts.keys():
            desc, typ = dmap_consts[k]
            entry = []
            entry.append(('mcnm', k))
            entry.append(('mcna', desc))
            entry.append(('mcty', typ))
            content_codes.append(('mdcl', entry))
        reply = [('mccr', [('mstt', DAAP_OK)] + content_codes)]
        return (DAAP_OK, reply, [])

    # Note: we don't support authentication at the moment, when we do
    # send a 401 if there's no password and the client will re-issue the
    # /login.
    def do_login(self):
        # XXX If we are full, what does the server return?
        session = self.server.new_session()
        if not session:
            return (DAAP_UNAVAILABLE, [], [])
        # Stash a copy in case clients pull the rug under us so we can
        # still clean up in that case.  See the finish() routine.  Note,
        # this copy is significant as this establishes us as the 'control'
        # connection.  Data connections (those that are used to stream media
        # only) do not have this, and so when their connections close the
        # session remains active until the 'control' is closed.
        self.session = session
        reply = []
        reply.append(('mlog', [('mstt', DAAP_OK), ('mlid', session)]))
        # XXX Should we reject the login if there is no user-agent?  Rhythmbox
        # doesn't send one for some reason.
        return (DAAP_OK, reply, [])

    def do_logout(self):
        session = self.get_session()
        if not session:
           return (DAAP_FORBIDDEN, [], [])
        self.server.del_session(session)

    # We don't support this but Rhythmbox sends this anyway.  Grr.
    def do_update(self):
        path, query = split_url_path(self.path)
        session = self.get_session()
        if not session:
            return (DAAP_FORBIDDEN, [], [])
        # UGH.  We should be updating this ... this is not supported at the 
        # moment.
        xxx_revision = 2
        reply = []
        reply.append(('mupd', [('mstt', DAAP_OK), ('musr', xxx_revision)]))
        return (DAAP_OK, reply, [])

    def do_stream_file(self, db_id, item_id, ext, chunk):
        rc = DAAP_OK
        extra_headers = []
        self.log_message('daap server: do_stream_file')
        seekpos = seekend = 0
        rangehdr = self.headers.getheader('Range')
        typ = ''
        if rangehdr:
            bytes = 'bytes='
            if rangehdr.startswith(bytes):
                seekpos = atol(rangehdr[len(bytes):])
                idx = rangehdr.find('-')
                if idx >= 0:
                    seekend = atol(rangehdr[(idx + 1):])
                if seekend < seekpos:
                    seekend = 0
                rc = DAAP_PARTIAL_CONTENT
        generation = threading.current_thread().generation
        file_obj = self.server.backend.get_file(item_id, generation, ext,
                                                self.get_session(),
                                                self.get_request_path,
                                                offset=seekpos, chunk=chunk)
        if not file_obj:
            return (DAAP_FILENOTFOUND, [], extra_headers)
        self.log_message('daap server: streaming with filobj %s', file_obj)
        # Return a special response, the encode_reponse() will handle correctly
        return (rc, [(file_obj, seekpos, seekend)], extra_headers)

    def get_request_path(self, itemid, enclosure):
        # XXX
        # This API is bad because we can't get the address we used to connect
        # with the client unless we poke into semi-private data.  Ugh.
        address, addrlength = self.rfile._sock.getsockname()
        listen_address, port = self.server.server_address
        return ('daap://%s:%d/databases/1/items/%d.%s?session-id=%d' % 
                (address, port, itemid, enclosure, self.get_session()))

    def do_databases(self):
        path, query = split_url_path(self.path)
        session = self.get_session()
        if not session:
            return (DAAP_FORBIDDEN, [], [])
        if len(path) == 1:
            reply = []
            db = []
            count = len(self.server.backend.get_items())
            name = self.server.name
            npl = 1 + len(self.server.backend.get_playlists())
            db.append(('mlit', [
                                ('miid', 1),    # Item ID
                                ('mper', 1),    # Persistent ID
                                ('minm', name), # Name
                                ('mimc', count),# Total count
                                # Playlist is always non-zero because of
                                # default playlist.
                                ('mctc', npl)   # Playlist count
                               ]))
            reply.append(('avdb', [
                                   ('mstt', DAAP_OK),   # OK
                                   ('muty', 0),         # Update type
                                   ('mtco', 1),         # Specified total count
                                   ('mrco', 1),         # Returned count
                                   ('mlcl', db)         # db listing
                                  ]))
            return (DAAP_OK, reply, [])
        else:
            # XXX might want to consider using regexp to do some complex
            # matching here.
            if path[2] == 'containers':
                return self.do_database_containers(path, query)
            elif path[2] == 'browse':
                return self.do_database_browse(path, query)
            elif path[2] == 'items':
                return self.do_database_items(path, query)
            elif path[2] == 'groups':
                return self.do_database_groups(path, query)
            else:
                return (DAAP_FORBIDDEN, [], [])

    def _check_db_id(self, db_id):
        return db_id == 1

    # do_database_xxx(self, path, query): helper functions.  Session already
    # checked and we know we are in database/xxx.
    def do_database_containers(self, path, query):
        db_id = int(path[1])
        if not self._check_db_id(db_id):
            return (DAAP_FORBIDDEN, [], [])
        reply = []
        if len(path) == 3:
            # There is a requirement to send a default playlist so we
            # try to always send that one.
            count = len(self.server.backend.get_items())
            default_playlist = [('mlit', [
                                          ('miid', 1),     # Item id
                                          ('minm', 'Library'),
                                          ('mper', 1),     # Persistent id
                                          ('mimc', count), # count
                                          ('mpco', 0),     # parent containerid
                                          ('abpl', 1)      # Base playlist 
                                         ]
                               )]
            playlists = self.server.backend.get_playlists()
            playlist_list = []
            try:
                meta = query['meta']
            except KeyError:
                meta = DEFAULT_DAAP_PLAYLIST_META
            meta_list = [m.strip() for m in meta.split(',')]
            for k in playlists.keys():
                playlistprop = playlists[k]
                playlist = []
                for m in meta_list:
                    if m in playlistprop.keys():
                        try:
                            code = dmap_consts_rmap[m]
                        except KeyError:
                            continue
                        if playlistprop[m] is not None:
                            attribute = (code, playlistprop[m])
                            playlist.append(attribute)
                playlist_list.append(('mlit', playlist))
                                          
            npl = 1 + len(playlists)
            reply.append(('aply', [                   # Database playlists
                                   ('mstt', DAAP_OK), # Status - OK
                                   ('muty', 0),       # Update type
                                   ('mtco', npl),     # total count
                                   ('mrco', npl),     # returned count
                                   ('mlcl', default_playlist + playlist_list)
                                  ]
                        ))
        else:
            # len(path) > 3
            playlist_id = int(path[3])
            return self.do_itemlist(path, query, playlist_id=playlist_id)
        return (DAAP_OK, reply, [])

    def do_database_browse(self, path, query):
        db_id = int(path[1])
        if not self._check_db_id(db_id):
            return (DAAP_FORBIDDEN, [], [])
        # XXX Browsing is not supported at the moment.
        return (DAAP_FORBIDDEN, [], [])

    # XXX TODO: a lot of junk we want to do here:
    # sort-headers - seems to be like asking the server to sort something
    # type=xxx - not parsed yet.  I don't think it's actually used (?)
    # try to invoke any of this the server will go BOH BOH!!!! no support!!!
    def do_itemlist(self, path, query, playlist_id=None):
        # Library playlist?
        # Save this variable, we use it to determine which code to send later
        # on.  playlist_id is Library default so it if asks for that as a 
        # container (playlist) we still want to send the playlist version.
        backend_id = playlist_id
        if backend_id == 1:
            backend_id = None
        items = self.server.backend.get_items(playlist_id=backend_id)
        nfiles = len(items)
        itemlist = []
        try:
            meta = query['meta']
        except KeyError:
            meta = DEFAULT_DAAP_META
        meta_list = [m.strip() for m in meta.split(',')]
        # NB: mikd must be the first guy in the listing.
        # GRR stupid Rhythmbox!  The meta reply must appear in order otherwise
        # it doesn't work!
        for k in items.keys():
            itemprop = items[k]
            item = []
            for m in meta_list:
                if m in itemprop.keys():
                    try:
                        code = dmap_consts_rmap[m]
                    except KeyError:
                        continue
                    if itemprop[m] is not None:
                        attribute = (code, itemprop[m])
                        item.append(attribute)
            itemlist.append(('mlit', [       # Listing item
                                      # item kind - seems OK to hardcode this.
                                      ('mikd', DAAP_ITEMKIND_AUDIO),
                                     ] + item
                           )) 
 
        tag = 'apso' if playlist_id else 'adbs'
        reply = []
        reply = [(tag, [                     # Container type
                        ('mstt', DAAP_OK),   # Status: OK
                        ('muty', 0),         # Update type
                        ('mtco', nfiles),    # Specified total count
                        ('mrco', nfiles),    # Returned count
                        ('mlcl', itemlist)   # Itemlist container
                       ]
                )]
        return (DAAP_OK, reply, [])

    def do_database_items(self, path, query):
        db_id = int(path[1])
        if not self._check_db_id(db_id):
            return (DAAP_FORBIDDEN, [], [])
        if len(path) == 3:
            # ^/database/id/items$
            return self.do_itemlist(path, query)
        if len(path) == 4:
            # Use atoi() here if only because Rhythmbox always pass us
            # junk at the end.
            item_id = atoi(path[3])
            self.log_message('daap server: now playing item %d', item_id)
            name, ext = os.path.splitext(path[3])
            ext = ext[1:]
            chunk = None
            if query.has_key('chunk'):
                chunk = int(query['chunk'])
            return self.do_stream_file(db_id, item_id, ext, chunk)

    def do_database_groups(self, path, query):
        db_id = int(path[1])
        if not self._check_db_id(db_id):
            return (DAAP_FORBIDDEN, [], [])

    def do_activity(self):
        # Getting the session automatically renews it for us.
        session = self.get_session()
        if not session:
            return (DAAP_FORBIDDEN, [], [])
        return (DAAP_NOCONTENT, [], [])

    def do_GET(self):
        # Farm off to the right request URI handler.
        # XXX jump table?
        # TODO XXX - add try: except block to protect against nasty
        # Handle iTunes 10 sending absolute path, and work around a limitation
        # in urlparse (doesn't support daap but it's basically the same
        # as http).
        endconn = False
        try:
            # You can do virtual host with this but we don't support for now
            # and actually strip it out.
            if self.path.startswith('daap://'):
                tmp = 'http://' + self.path[len('daap://'):]
                result = urlparse.urlparse(tmp)
                # XXX shouldn't overwrite this but we'll fix it later
                if result.query:
                    self.path = '?'.join([result.path, result.query])
                else:
                    self.path = result.path
            if self.path == '/server-info':
                rcode, reply, extra_headers = self.do_server_info()
            elif self.path == '/content-codes':
                rcode, reply, extra_headers = self.do_content_codes()
            elif self.path == '/login':
                rcode, reply, extra_headers = self.do_login()
            # /activity?session-id=xxxxx
            # XXX we should be splitting these so the path and the querystring
            # are separate.
            elif self.path.startswith('/logout'):
               self.do_logout()
               endconn = True
            elif self.path.startswith('/activity'):
                rcode, reply, extra_headers = self.do_activity()
            elif self.path.startswith('/update'):
                rcode, reply, extra_headers = self.do_update()
            elif self.path.startswith('/databases'):
                rcode, reply, extra_headers = self.do_databases()
            else:
                # Boh-boh.  Unrecognized URI.  Send HTTP/1.1 bad request 400.
                rcode = DAAP_BADREQUEST
                reply = []
                extra_headers = []
        except Exception, e:
            self.log_message('Error: Exception occurred: ' + str(e))
            if self.server.debug:
                (typ, value, tb) = sys.exc_info()
                print 'Exception: ' + str(typ)
                print 'Traceback:\n'
                traceback.print_tb(tb)
            # XXX should we end the connection on an exception occurence?
            rcode = DAAP_BADREQUEST
            reply = []
            extra_headers = []
        if endconn:
            self.wfile.close()
        else:
            self.do_send_reply(rcode, reply, extra_headers=extra_headers)

def mdns_init():
    return mdns.mdns_init()

# install_mdns: returns a callback object.  Call the get_refs() method
# and pass it to select to test for readability, then invoke the object
# directly passing a readable socket (one at a time) which will take care of
# calling your supplied callback internally in due course.  Note: do NOT 
# assume when select returns and you call the callback object your supplied
# callback is called because there may be insufficient data, for example.
def mdns_register_service(name, register_callback,
                          service='_daap._tcp', port=DEFAULT_PORT):
    class RegisterCallback(object):
        def __init__(self, user_callback):
            self.user_callback = user_callback

        def mdns_register_callback(self, sdRef, flags, errorCode, name,
                                   regtype, domain):
            # XXX error handling?
            if errorCode != mdns.pybonjour.kDNSServiceErr_NoError:
                pass
            else:
                self.user_callback(name)
    register_callback_obj = RegisterCallback(register_callback)
    return mdns.bonjour_register_service(name, '_daap._tcp', port=port,
        callback=register_callback_obj.mdns_register_callback)

def mdns_unregister_service(mdns_object):
    mdns_object.close()

def mdns_browse(callback):
    # This class allows us to make a callback and then do some post-processing
    # before we really pass the stuff back to the user.  We need it because
    # we need some place to stash the user callback.  Our aim isn't to return
    # exactly what's returned by the mDNSResponder API but to return what's
    # useful to us, and that means some text processing.
    class BrowseCallback(object):
       def __init__(self, callback):
           self.user_callback = callback
       def mdns_callback(self, added, fullname, hosttarget, port):
           # XXX not exactly sure why it does this, but we can fix it up.
           # If there's something we can convert back to ASCII then just skip
           # over.
           for x in xrange(0, 0x100):
               try:
                   fullname = fullname.replace('\\%03d' % x, chr(x))
               except UnicodeDecodeError:
                   continue
           # Strip away the '_daap._tcp...'
           try:
               fullname = fullname[:fullname.rindex('._daap._tcp')]
           except (ValueError, IndexError):
               pass
           self.user_callback(added, fullname, hosttarget, port)
    callback_obj = BrowseCallback(callback)
    mdns_callback = callback_obj.mdns_callback
    return mdns.bonjour_browse_service('_daap._tcp', mdns_callback)

def runloop(daapserver):
    daapserver.serve_forever()

def make_daap_server(backend, debug=False, name='pydaap', port=DEFAULT_PORT,
                     max_conn=DAAP_MAXCONN, robust=True):
    handler = DaapHttpRequestHandler
    failed = False
    while True:
        try:
            httpd = DaapTCPServer(('', port), handler)
            break
        except socket.error, e:
            if robust and not port == 0:
                port = 0
                continue
            failed = True
            break
    if failed:
        return None

    httpd.set_debug(debug) 
    httpd.set_name(name)
    httpd.set_backend(backend)
    httpd.set_maxconn(max_conn)
    return httpd

###############################################################################

# DaapClient class
#
# TODO Should check daap status codes - but it's duplicated in the http
# response as well, so it's not very urgent.
#
# Proposed locking protocol: there is a main lock around the HTTPConnection 
# object, everytime you access it via a request/response pair you should 
# wrap this around a lock.  Disconnection detection is done via a watcher 
# which uses select() to poll the socket for readability.  When the socket
# returns readable, it locks the connection to check for self.sock = None.
# If it's None then it's been closed.  Alternatively, if it is not, then
# we do a select on this socket with a zero timeout.  If no error is
# encountered it means the socket is closed.  This assumes that you are using
# HTTP/1.1.
class DaapClient(object):
    HEARTBEAT = 60    # seconds
    def __init__(self, host, port):
        self.conn = None
        self.host = host
        self.port = port
        self.session = None

    # Caveat emptor when using it.
    # if (test) { do_something(); } is NOT SAFE generally!
    def alive(self):
        # XXX dodgy: pokes into the sock of HTTPConnection but we have no
        # choice.
        if not self.conn or not self.conn.sock:
            return False
        sock = self.conn.sock
        buf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVLOWAT)
        while True:
            try:
                data = sock.recv(buf, socket.MSG_PEEK)
            except socket.error, (err, errstring):
                if err == errno.EAGAIN:
                    return True
                # Anything else we treat as a connection failure.
                if err in (errno.EINTR, errno.ENOBUFS):
                    continue
                return False

    def heartbeat_callback(self):
        try:
            # NB: This is a third connection in addition to the control
            # and a data connection which may already be running.  I think
            # this sits well with most implementations?
            tmp_conn = httplib.HTTPConnection(self.host, self.port)
            tmp_conn.request('GET', self.sessionize('/activity', []))
            self.check_reply(tmp_conn.getresponse(), httplib.NO_CONTENT)
            # If it works, Re-arm the timer
            self.timer = threading.Timer(self.HEARTBEAT,
                                         self.heartbeat_callback)
            self.timer.start()
        # We've been disconnected, or server gave incorrect response?
        except (IOError, ValueError):
            self.disconnect()

    # Generic check for http response.  ValueError() on unexpected response.
    def check_reply(self, response, http_code=httplib.OK, callback=None,
                    args=[]):
        if response.status != http_code:
            raise ValueError('Unexpected response code %d' % http_code)
        if response.version != 11:
            raise ValueError('Server did not return HTTP/1.1')
        # XXX Broken - don't do an unbounded read here, this is stupid,
        # server can crash the client
        data = response.read()
        if callback:
            callback(data, *args)

    def handle_login(self, data):
        self.session = find_daap_tag('mlid', decode_response(data))

    # Note: in theory there could be multiple DB but in reality there's only
    # one.  So this is a shortcut.
    def handle_db(self, data):
        db_list = find_daap_tag('mlcl', decode_response(data))
        # Just get the first one.
        db = find_daap_tag('mlit', db_list)
        self.db_id = find_daap_tag('miid', db)
        self.db_name = find_daap_tag('minm', db)

    def handle_playlist(self, data, meta):
        listing = find_daap_tag('mlcl', decode_response(data))
        playlist_dict = dict()
        meta_list = [m.strip() for m in meta.split(',')]
        for item in find_daap_listitems(listing):
            playlist_id = find_daap_tag('miid', item)
            playlist_dict[playlist_id] = dict()
            for m in meta_list:
                try:
                    playlist_dict[playlist_id][m] = find_daap_tag(
                                                    dmap_consts_rmap[m], item)
                except KeyError:
                    continue
        self.daap_playlists = playlist_dict

    def handle_items(self, data, playlist_id, meta):
        listing = find_daap_tag('mlcl', decode_response(data))
        itemdict = dict()
        if not listing:
            self.daap_items = dict()    # dummy empty
            return
        meta_list = [m.strip() for m in meta.split(',')]
        for item in find_daap_listitems(listing):
            itemid = find_daap_tag('miid', item)
            itemdict[itemid] = dict()
            for m in meta_list:
                try:
                    itemdict[itemid][m] = find_daap_tag(
                                          dmap_consts_rmap[m], item)
                except KeyError:
                    continue
        self.daap_items = itemdict

    def sessionize(self, request, query):
        if not self.session:
            raise ValueError('no session (not logged in?)')
        new_request = request + '?session-id=%d' % self.session
        # XXX urllib.quote?
        new_request = '&'.join([new_request] + 
                               [name + '=' + param for name, param in query])
        return new_request

    def connect(self):
        try:
            self.conn = httplib.HTTPConnection(self.host, self.port)
            self.conn.request('GET', '/server-info')
            self.check_reply(self.conn.getresponse())            
            self.conn.request('GET', '/content-codes')
            self.check_reply(self.conn.getresponse())
            self.conn.request('GET', '/login')
            self.check_reply(self.conn.getresponse(),
                             callback=self.handle_login)
            # Finally, if this all works, start the heartbeat timer.
            # XXX pick out the daap timeout from the server.
            self.timer = threading.Timer(self.HEARTBEAT,
                                         self.heartbeat_callback)
            self.timer.start()
            return True
        # We've been disconnected or there was a problem?
        except (socket.error, IOError, ValueError):
            self.disconnect()
            return False
        except httplib.BadStatusLine:
            self.disconnect(polite=False)
            return False

    # XXX Right now, there is only one db_id.
    def databases(self):
        try:
            self.conn.request('GET', self.sessionize('/databases', []))
            self.check_reply(self.conn.getresponse(),
                             callback=self.handle_db)
            return self.db_id
        # We've been disconnected or there was a problem?
        except (socket.error, IOError, ValueError):
            self.disconnect()
            return None
        except httplib.BadStatusLine:
            self.disconnect(polite=False)
            return None

    def playlists(self, meta=DEFAULT_DAAP_PLAYLIST_META):
        try:
            self.conn.request('GET', self.sessionize(
                              '/databases/%d/containers' % self.db_id,
                              [('meta', meta)]))
            self.check_reply(self.conn.getresponse(),
                             callback=self.handle_playlist,
                             args=[meta])
            playlists = self.daap_playlists
            del self.daap_playlists
            return playlists
        # We've been disconnected or there was a problem?
        except (socket.error, IOError, ValueError):
            self.disconnect()
            return None
        except httplib.BadStatusLine:
            self.disconnect(polite=False)
            return None

    # XXX: I think this could be cleaner, maybe abstract to have an
    # easy way to provide the daap meta without resorting to providing
    # the raw string which includes the names requested.
    def items(self, playlist_id=None, meta=DEFAULT_DAAP_META):
        try:
            if playlist_id is None:
                self.conn.request('GET', self.sessionize(
                    '/databases/%d/items' % self.db_id,
                    [('meta', meta)]))
            else:
                self.conn.request('GET', self.sessionize(
                    ('/databases/%d/containers/%d/items' % 
                     (self.db_id, playlist_id)),
                    [('meta', meta)]))
            self.check_reply(self.conn.getresponse(),
                             callback=self.handle_items,
                             args=[playlist_id, meta])
            items = self.daap_items
            del self.daap_items
            return items
        # We've been disconnected or there was a problem?
        except (socket.error, IOError, ValueError):
            typ, value, tb = sys.exc_info()
            print 'items: typ = %s value = %s' % (str(typ), str(value))
            for line in traceback.format_tb(tb):
                print line
            self.disconnect()
            return None
        except httplib.BadStatusLine:
            self.disconnect(polite=False)
            return None

    def disconnect(self, polite=True):
        try:
            self.timer.cancel()
            if polite:
                self.conn.request('GET', self.sessionize('/logout', []))
        # Don't care since we are going away anyway.
        except (socket.error, ValueError, httplib.ResponseNotReady,
                httplib.BadStatusLine, AttributeError, IOError):
            pass
        finally:
            self.session = None
            self.conn.close()
            self.conn = None

    def daap_get_file_request(self, file_id, enclosure=None):
        """daap_file_get_url(file_id) -> url
        Helper function to convert from a file id to a http request that we can
        use to download stuff.

        It's useful to remember that daap is just http, so you can use any http
        client you like here.
        """
        if not enclosure:
            enclosure = 'mp3'    # Assume if None
        fn = '/databases/%d/items/%d.%s' % (self.db_id, file_id, enclosure)
        fn += '?session-id=%s' % self.session
        return fn

def make_daap_client(host, port=DEFAULT_PORT):
    return DaapClient(host, port)
