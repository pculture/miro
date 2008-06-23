# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""Format strings to send to the user."""

import math
import datetime

from miro.gtcache import gettext as _
from miro.gtcache import ngettext

def download_rate(rate):
    if rate >= (1 << 30):
        return _("%sGB/s") % ("%.1f" % (rate / float(1 << 30)))
    elif rate >= (1 << 20):
        return _("%sMB/s") % ("%.1f" % (rate / float(1 << 20)))
    elif rate >= (1 << 10):
        return _("%sKB/s") % ("%.1f" % (rate / float(1 << 10)))
    else:
        return _("%sB/s") % (rate)

def time(secs):
    if secs > 3600:
        hours, secs = divmod(secs, 3600)
        minutes, seconds = divmod(secs, 60)
        return '%02d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%02d:%02d' % divmod(secs, 60)

def size(bytes):
    if bytes >= (1 << 30):
        return _("%sGB") % ("%.1f" % (bytes / float(1 << 30)))
    elif bytes >= (1 << 20):
        return _("%sMB") % ("%.1f" % (bytes / float(1 << 20)))
    elif bytes >= (1 << 10):
        return _("%sKB") % ("%.1f" % (bytes / float(1 << 10)))
    else:
        return _("%sB") % (bytes)

def expiration_date(expiration_date):
    offset = expiration_date - datetime.datetime.now()
    if offset.days > 0:
        return ngettext("Expires in %d day", "Expires in %d days",
                offset.days) % offset.days
    elif offset.seconds > 3600:
        return ngettext("Expires in %d hour", "Expires in %d hour",
                offset.days) % math.ceil(offset.seconds/3600.0)
    else:
        return ngettext("Expires in %d minute", "Expires in %d minute",
                offset.days) % math.ceil(offset.seconds/60.0)
