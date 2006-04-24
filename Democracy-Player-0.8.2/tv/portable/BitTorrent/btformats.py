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

import re

from BitTorrent import BTFailure

allowed_path_re = re.compile(r'^[^/\\.~][^/\\]*$')

ints = (long, int)

def check_info(info, check_paths=True):
    if type(info) != dict:
        raise BTFailure, 'bad metainfo - not a dictionary'
    pieces = info.get('pieces')
    if type(pieces) != str or len(pieces) % 20 != 0:
        raise BTFailure, 'bad metainfo - bad pieces key'
    piecelength = info.get('piece length')
    if type(piecelength) not in ints or piecelength <= 0:
        raise BTFailure, 'bad metainfo - illegal piece length'
    name = info.get('name')
    if type(name) != str:
        raise BTFailure, 'bad metainfo - bad name'
    if not allowed_path_re.match(name):
        raise BTFailure, 'name %s disallowed for security reasons' % name
    if info.has_key('files') == info.has_key('length'):
        raise BTFailure, 'single/multiple file mix'
    if info.has_key('length'):
        length = info.get('length')
        if type(length) not in ints or length < 0:
            raise BTFailure, 'bad metainfo - bad length'
    else:
        files = info.get('files')
        if type(files) != list:
            raise BTFailure, 'bad metainfo - "files" is not a list of files'
        for f in files:
            if type(f) != dict:
                raise BTFailure, 'bad metainfo - bad file value'
            length = f.get('length')
            if type(length) not in ints or length < 0:
                raise BTFailure, 'bad metainfo - bad length'
            path = f.get('path')
            if type(path) != list or path == []:
                raise BTFailure, 'bad metainfo - bad path'
            for p in path:
                if type(p) != str:
                    raise BTFailure, 'bad metainfo - bad path dir'
                if check_paths and not allowed_path_re.match(p):
                    raise BTFailure, 'path %s disallowed for security reasons' % p
        f = ['/'.join(x['path']) for x in files]
        f.sort()
        i = iter(f)
        try:
            name2 = i.next()
            while True:
                name1 = name2
                name2 = i.next()
                if name2.startswith(name1):
                    if name1 == name2:
                        raise BTFailure, 'bad metainfo - duplicate path'
                    elif name2[len(name1)] == '/':
                        raise BTFailure('bad metainfo - name used as both '
                                        'file and subdirectory name')
        except StopIteration:
            pass

def check_message(message, check_paths=True):
    if type(message) != dict:
        raise BTFailure, 'bad metainfo - wrong object type'
    check_info(message.get('info'), check_paths)
    if type(message.get('announce')) != str:
        raise BTFailure, 'bad metainfo - no announce URL string'

def check_peers(message):
    if type(message) != dict:
        raise BTFailure
    if message.has_key('failure reason'):
        if type(message['failure reason']) != str:
            raise BTFailure, 'non-text failure reason'
        return
    if message.has_key('warning message'):
        if type(message['warning message']) != str:
            raise BTFailure, 'non-text warning message'
    peers = message.get('peers')
    if type(peers) == list:
        for p in peers:
            if type(p) != dict:
                raise BTFailure, 'invalid entry in peer list'
            if type(p.get('ip')) != str:
                raise BTFailure, 'invalid entry in peer list'
            port = p.get('port')
            if type(port) not in ints or p <= 0:
                raise BTFailure, 'invalid entry in peer list'
            if p.has_key('peer id'):
                peerid = p.get('peer id')
                if type(peerid) != str or len(peerid) != 20:
                    raise BTFailure, 'invalid entry in peer list'
    elif type(peers) != str or len(peers) % 6 != 0:
        raise BTFailure, 'invalid peer list'
    interval = message.get('interval', 1)
    if type(interval) not in ints or interval <= 0:
        raise BTFailure, 'invalid announce interval'
    minint = message.get('min interval', 1)
    if type(minint) not in ints or minint <= 0:
        raise BTFailure, 'invalid min announce interval'
    if type(message.get('tracker id', '')) != str:
        raise BTFailure, 'invalid tracker id'
    npeers = message.get('num peers', 0)
    if type(npeers) not in ints or npeers < 0:
        raise BTFailure, 'invalid peer count'
    dpeers = message.get('done peers', 0)
    if type(dpeers) not in ints or dpeers < 0:
        raise BTFailure, 'invalid seed count'
    last = message.get('last', 0)
    if type(last) not in ints or last < 0:
        raise BTFailure, 'invalid "last" entry'
