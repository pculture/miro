# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Uoti Urpala

from time import time

class RateLimiter(object):

    def __init__(self, sched):
        self.sched = sched
        self.last = None
        self.upload_rate = 1e10
        self.unitsize = 1e10
        self.offset_amount = 0

    def set_parameters(self, rate, unitsize):
        if rate == 0:
            rate = 1e10
            unitsize = 17000
        if unitsize > 17000:
            # Since data is sent to peers in a round-robin fashion, max one
            # full request at a time, setting this higher would send more data
            # to peers that use request sizes larger than standard 16 KiB.
            # 17000 instead of 16384 to allow room for metadata messages.
            unitsize = 17000
        self.upload_rate = rate * 1024
        self.unitsize = unitsize
        self.lasttime = time()
        self.offset_amount = 0

    def queue(self, conn):
        assert conn.next_upload is None
        if self.last is None:
            self.last = conn
            conn.next_upload = conn
            self.try_send(True)
        else:
            conn.next_upload = self.last.next_upload
            self.last.next_upload = conn
            self.last = conn

    def try_send(self, check_time=False):
        t = time()
        self.offset_amount -= (t - self.lasttime) * self.upload_rate
        self.lasttime = t
        if check_time:
            self.offset_amount = max(self.offset_amount, 0)
        cur = self.last.next_upload
        while self.offset_amount <= 0:
            try:
                bytes = cur.send_partial(self.unitsize)
            except KeyboardInterrupt:
                raise
            except Exception, e:
                cur.encoder.context.got_exception(e)
                bytes = 0

            self.offset_amount += bytes
            if bytes == 0 or not cur.connection.is_flushed():
                if self.last is cur:
                    self.last = None
                    cur.next_upload = None
                    break
                else:
                    self.last.next_upload = cur.next_upload
                    cur.next_upload = None
                    cur = self.last.next_upload
            else:
                self.last = cur
                cur = cur.next_upload
        else:
            self.sched(self.try_send, self.offset_amount / self.upload_rate)

    def clean_closed(self):
        if self.last is None:
            return
        class Dummy(object):
            def __init__(self, next):
                self.next_upload = next
            def send_partial(self, size):
                return 0
            closed = False
        orig = self.last
        if self.last.closed:
            self.last = Dummy(self.last.next_upload)
        c = self.last
        while True:
            if c.next_upload is orig:
                c.next_upload = self.last
                break
            if c.next_upload.closed:
                c.next_upload = Dummy(c.next_upload.next_upload)
            c = c.next_upload
