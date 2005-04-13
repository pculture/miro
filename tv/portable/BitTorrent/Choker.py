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

from random import randrange

class Choker(object):

    def __init__(self, config, schedule, done = lambda: False):
        self.config = config
        self.schedule = schedule
        self.connections = []
        self.count = 0
        self.done = done
        self.unchokes_since_last = 0
        schedule(self._round_robin, 10)

    def _round_robin(self):
        self.schedule(self._round_robin, 10)
        self.count += 1
        if self.done():
            self._rechoke_seed(True)
            return
        if self.count % 3 == 0:
            for i in xrange(len(self.connections)):
                u = self.connections[i].upload
                if u.choked and u.interested:
                    self.connections = self.connections[i:] + self.connections[:i]
                    break
        self._rechoke()

    def _rechoke(self):
        if self.done():
            self._rechoke_seed()
            return
        preferred = []
        for i in xrange(len(self.connections)):
            c = self.connections[i]
            if c.upload.interested and not c.download.is_snubbed():
                preferred.append((-c.download.get_rate(), i))
        preferred.sort()
        prefcount = min(len(preferred), self.config['max_uploads_internal'] -1)
        mask = [0] * len(self.connections)
        for _, i in preferred[:prefcount]:
            mask[i] = 1
        count = max(1, self.config['min_uploads'] - prefcount)
        for i in xrange(len(self.connections)):
            c = self.connections[i]
            u = c.upload
            if mask[i]:
                u.unchoke(self.count)
            elif count > 0:
                u.unchoke(self.count)
                if u.interested:
                    count -= 1
            else:
                u.choke()

    def _rechoke_seed(self, force_new_unchokes = False):
        if force_new_unchokes:
            # number of unchokes per 30 second period
            i = (self.config['max_uploads_internal'] + 2) // 3
            # this is called 3 times in 30 seconds, if i==4 then unchoke 1+1+2
            # and so on; substract unchokes recently triggered by disconnects
            num_force_unchokes = max(0, (i + self.count % 3) // 3 - \
                                 self.unchokes_since_last)
        else:
            num_force_unchokes = 0
        preferred = []
        new_limit = self.count - 3
        for i in xrange(len(self.connections)):
            c = self.connections[i]
            u = c.upload
            if not u.choked and u.interested:
                if u.unchoke_time > new_limit or (
                        u.buffer and c.connection.is_flushed()):
                    preferred.append((-u.unchoke_time, -u.get_rate(), i))
                else:
                    preferred.append((1, -u.get_rate(), i))
        num_kept = self.config['max_uploads_internal'] - num_force_unchokes
        assert num_kept >= 0
        preferred.sort()
        preferred = preferred[:num_kept]
        mask = [0] * len(self.connections)
        for _, _, i in preferred:
            mask[i] = 1
        num_nonpref = self.config['max_uploads_internal'] - len(preferred)
        if force_new_unchokes:
            self.unchokes_since_last = 0
        else:
            self.unchokes_since_last += num_nonpref
        last_unchoked = None
        for i in xrange(len(self.connections)):
            c = self.connections[i]
            u = c.upload
            if not mask[i]:
                if not u.interested:
                    u.choke()
                elif u.choked:
                    if num_nonpref > 0 and c.connection.is_flushed():
                        u.unchoke(self.count)
                        num_nonpref -= 1
                        if num_nonpref == 0:
                            last_unchoked = i
                else:
                    if num_nonpref == 0:
                        u.choke()
                    else:
                        num_nonpref -= 1
                        if num_nonpref == 0:
                            last_unchoked = i
        if last_unchoked is not None:
            self.connections = self.connections[last_unchoked + 1:] + \
                               self.connections[:last_unchoked + 1]

    def connection_made(self, connection):
        p = randrange(len(self.connections) + 1)
        self.connections.insert(p, connection)

    def connection_lost(self, connection):
        self.connections.remove(connection)
        if connection.upload.interested and not connection.upload.choked:
            self._rechoke()

    def interested(self, connection):
        if not connection.upload.choked:
            self._rechoke()

    def not_interested(self, connection):
        if not connection.upload.choked:
            self._rechoke()
