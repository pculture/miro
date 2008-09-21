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
        value = "%1.1f" % (rate / float(1 << 30))
        return _("%(size)sGB/s", {"size": value})
    elif rate >= (1 << 20):
        value = "%1.1f" % (rate / float(1 << 20))
        return _("%(size)sMB/s", {"size": value})
    elif rate >= (1 << 10):
        value = "%1.1f" % (rate / float(1 << 10))
        return _("%(size)sKB/s", {"size": value})
    else:
        value = "%1.1f" % rate
        return _("%(size)sB/s", {"size": value})

def time(secs):
    if secs > 3600:
        hours, secs = divmod(secs, 3600)
        minutes, seconds = divmod(secs, 60)
        return '%02d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%02d:%02d' % divmod(secs, 60)

def size(bytes):
    # when switching from the enclosure reported size to the downloader
    # reported size, it takes a while to get the new size and the downloader
    # returns -1.  the user sees the size go to -1B which is weird....
    # better to return an empty string.
    if bytes == -1:
        return ""

    # FIXME this is a repeat of util.formatSizeForUser ...  should
    # probably ditch one of them.
    if bytes >= (1 << 30):
        value = "%.1f" % (bytes / float(1 << 30))
        return _("%(size)sGB", {"size": value})
    elif bytes >= (1 << 20):
        value = "%.1f" % (bytes / float(1 << 20))
        return _("%(size)sMB", {"size": value})
    elif bytes >= (1 << 10):
        value = "%.1f" % (bytes / float(1 << 10))
        return _("%(size)sKB", {"size": value})
    else:
        return _("%(size)sB", {"size": bytes})

def expiration_date(exp_date):
    offset = exp_date - datetime.datetime.now()
    if offset.days > 0:
        return ngettext("Expires in %(count)d day",
                        "Expires in %(count)d days",
                        offset.days,
                        {"count": offset.days})
    elif offset.seconds > 3600:
        return ngettext("Expires in %(count)d hour",
                        "Expires in %(count)d hours",
                        math.ceil(offset.seconds/3600.0),
                        {"count": math.ceil(offset.seconds/3600.0)})
    else:
        return ngettext("Expires in %(count)d minute",
                        "Expires in %(count)d minutes",
                        math.ceil(offset.seconds/60.0),
                        {"count": math.ceil(offset.seconds/60.0)})
