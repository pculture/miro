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

from time import time


class Measure(object):

    def __init__(self, max_rate_period, fudge=5):
        self.max_rate_period = max_rate_period
        self.ratesince = time() - fudge
        self.last = self.ratesince
        self.rate = 0.0
        self.total = 0

    def update_rate(self, amount):
        self.total += amount
        t = time()
        self.rate = (self.rate * (self.last - self.ratesince) + 
            amount) / (t - self.ratesince)
        self.last = t
        if self.ratesince < t - self.max_rate_period:
            self.ratesince = t - self.max_rate_period

    def get_rate(self):
        self.update_rate(0)
        return self.rate

    def get_rate_noupdate(self):
        return self.rate

    def time_until_rate(self, newrate):
        if self.rate <= newrate:
            return 0
        t = time() - self.ratesince
        return ((self.rate * t) / newrate) - t

    def get_total(self):
        return self.total
