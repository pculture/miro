# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

from __future__ import generators

import sys
if sys.version_info < (2, 3):
    # Allow int() to create numbers larger than "small ints".
    # This is NOT SAFE if int is used as the name of the type instead
    # (as in "type(x) in (int, long)").
    int = long

    def enumerate(x):
        i = 0
        for y in x:
            yield (i, y)
            i += 1

    def sum(seq):
        r = 0
        for x in seq:
            r += x
        return r

del sys
