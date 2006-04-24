# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by John Hoffman and Uoti Urpala

import os
from sha import sha

from BitTorrent.bencode import bencode, bdecode
from BitTorrent.btformats import check_message

NOISY = False

def parsedir(directory, parsed, files, blocked, errfunc,
             include_metainfo=True):
    if NOISY:
        errfunc('checking dir')
    dirs_to_check = [directory]
    new_files = {}
    new_blocked = {}
    while dirs_to_check:    # first, recurse directories and gather torrents
        directory = dirs_to_check.pop()
        newtorrents = False
        try:
            dir_contents = os.listdir(directory)
        except (IOError, OSError), e:
            errfunc("Could not read directory " + directory)
            continue
        for f in dir_contents:
            if f.endswith('.torrent'):
                newtorrents = True
                p = os.path.join(directory, f)
                try:
                    new_files[p] = [(os.path.getmtime(p),os.path.getsize(p)),0]
                except (IOError, OSError), e:
                    errfunc("Could not stat " + p + " : " + str(e))
        if not newtorrents:
            for f in dir_contents:
                p = os.path.join(directory, f)
                if os.path.isdir(p):
                    dirs_to_check.append(p)

    new_parsed = {}
    to_add = []
    added = {}
    removed = {}
    # files[path] = [(modification_time, size), hash], hash is 0 if the file
    # has not been successfully parsed
    for p,v in new_files.items():   # re-add old items and check for changes
        oldval = files.get(p)
        if oldval is None:     # new file
            to_add.append(p)
            continue
        h = oldval[1]
        if oldval[0] == v[0]:   # file is unchanged from last parse
            if h:
                if p in blocked:      # parseable + blocked means duplicate
                    to_add.append(p)  # other duplicate may have gone away
                else:
                    new_parsed[h] = parsed[h]
                new_files[p] = oldval
            else:
                new_blocked[p] = None  # same broken unparseable file
            continue
        if p not in blocked and h in parsed:  # modified; remove+add
            if NOISY:
                errfunc('removing '+p+' (will re-add)')
            removed[h] = parsed[h]
        to_add.append(p)

    to_add.sort()
    for p in to_add:                # then, parse new and changed torrents
        new_file = new_files[p]
        v = new_file[0]
        if new_file[1] in new_parsed:  # duplicate
            if p not in blocked or files[p][0] != v:
                errfunc('**warning** '+ p + ' is a duplicate torrent for ' +
                        new_parsed[new_file[1]]['path'])
            new_blocked[p] = None
            continue

        if NOISY:
            errfunc('adding '+p)
        try:
            ff = open(p, 'rb')
            d = bdecode(ff.read())
            check_message(d)
            h = sha(bencode(d['info'])).digest()
            new_file[1] = h
            if new_parsed.has_key(h):
                errfunc('**warning** '+ p +
                        ' is a duplicate torrent for '+new_parsed[h]['path'])
                new_blocked[p] = None
                continue

            a = {}
            a['path'] = p
            f = os.path.basename(p)
            a['file'] = f
            i = d['info']
            l = 0
            nf = 0
            if i.has_key('length'):
                l = i.get('length',0)
                nf = 1
            elif i.has_key('files'):
                for li in i['files']:
                    nf += 1
                    if li.has_key('length'):
                        l += li['length']
            a['numfiles'] = nf
            a['length'] = l
            a['name'] = i.get('name', f)
            def setkey(k, d = d, a = a):
                if d.has_key(k):
                    a[k] = d[k]
            setkey('failure reason')
            setkey('warning message')
            setkey('announce-list')
            if include_metainfo:
                a['metainfo'] = d
        except:
            errfunc('**warning** '+p+' has errors')
            new_blocked[p] = None
            continue
        try:
            ff.close()
        except:
            pass
        if NOISY:
            errfunc('... successful')
        new_parsed[h] = a
        added[h] = a

    for p,v in files.iteritems():       # and finally, mark removed torrents
        if p not in new_files and p not in blocked:
            if NOISY:
                errfunc('removing '+p)
            removed[v[1]] = parsed[v[1]]

    if NOISY:
        errfunc('done checking')
    return (new_parsed, new_files, new_blocked, added, removed)
