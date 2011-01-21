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

# mdns.py
#

import select
import socket
import errno
import sys

# mdns_init(): adapted for Miro: pybonjour is always available.
def mdns_init():
    try:
        import pybonjour
    except ImportError:
        from miro import pybonjour
    global pybonjour
    return True

# Dummy object
class HostObject(object):
    pass

# Use a Python class so we can stash our state inside it.
class BonjourCallbacks(object):
    def __init__(self, user_callback):
        self.user_callback = user_callback
        self.refs = []
        self.query_types = [pybonjour.kDNSServiceType_A]
        # Workaround: the Windows mDNSResponder won't give us a reply
        # for type AAAA!  Is it because there is no IPv6 configured?
        # mDNSResponder should still return error in this case.
        if sys.platform != 'win32':
            self.query_types.append(pybonjour.kDNSServiceType_AAAA)
        self.nquery_types = len(self.query_types)

    def add_ref(self, ref):
        self.refs.append(ref)

    def del_ref(self, ref):
        self.refs.remove(ref)

    def get_refs(self):
        return self.refs

    def close(self):
        for ref in self.refs:
            ref.close()

    def __call__(self, ref):
        pybonjour.DNSServiceProcessResult(ref)

    def register_callback(self, sdRef, flags, errorCode, name, regtype,
                               domain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return
        self.user_callback(sdRef, flags, errorCode, name, regtype, domain)

    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode,
                        serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        host = HostObject()
        if (flags & pybonjour.kDNSServiceFlagsAdd):
            host.added = True
        else:
            host.added = False

        ref = pybonjour.DNSServiceResolve(0,
                                          interfaceIndex,
                                          serviceName,
                                          regtype,
                                          replyDomain,
                                          self.resolve_callback)
        self.host[ref.fileno()] = host
        self.add_ref(ref)

    def query_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname,
                       rrtype, rrclass, rdata, ttl):
        idx = sdRef.fileno()
        self.host[idx].typecount += 1
        af = socket.AF_UNSPEC
        if rrtype == pybonjour.kDNSServiceType_AAAA:
            af = socket.AF_INET6
        elif rrtype == pybonjour.kDNSServiceType_A:
            af = socket.AF_INET
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            self.host[idx].ips[af] = rdata
        if self.nquery_types == self.host[idx].typecount:
            self.user_callback(self.host[idx].added,
                               self.host[idx].fullname,
                               self.host[idx].hosttarget,
                               self.host[idx].ips,
                               self.host[idx].port)
        del self.host[idx]
        self.del_ref(sdRef)
        sdRef.close()

    def resolve_callback(self, sdRef, flags, interfaceIndex, errorCode,
                         fullname, hosttarget, port, txtRecord):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            old_idx = sdRef.fileno()
            for typ in self.query_types:
                ref = pybonjour.DNSServiceQueryRecord(
                                              interfaceIndex = interfaceIndex,
                                              fullname = hosttarget,
                                              rrtype = typ,
                                              callBack = self.query_callback)
                # Move this guy to a new indexing slot, we are about to be 
                # done with this socket.  We add an index entry for each
                # reference all pointing to the same host object because 
                # we can't reconstruct a index on a per-host basis in 
                # the callback.
                idx = ref.fileno()
                self.host[idx] = self.host[old_idx]
                self.add_ref(ref)

            # Housekeeping: delete the old index because the socket will be
            # closed.
            host = self.host[old_idx]
            del self.host[old_idx]
            host.typecount = 0
            host.fullname = fullname
            host.hosttarget = hosttarget
            host.port = port
            host.ips = dict()

        self.del_ref(sdRef)
        sdRef.close()

def bonjour_register_service(name, regtype, port, callback):
    callback_obj = BonjourCallbacks(callback)
    ref = pybonjour.DNSServiceRegister(name=name,
                                       regtype=regtype,
                                       port=port,
                                       callBack=callback_obj.register_callback)
    callback_obj.add_ref(ref)
    return callback_obj

def bonjour_browse_service(regtype, callback):
    callback_obj = BonjourCallbacks(callback)
    ref = pybonjour.DNSServiceBrowse(regtype=regtype,
                                     callBack=callback_obj.browse_callback)
    callback_obj.host = dict()
    callback_obj.add_ref(ref)
    return callback_obj
