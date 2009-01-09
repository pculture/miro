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
        return _("%(size)s gb/s", {"size": value})
    elif rate >= (1 << 20):
        value = "%1.1f" % (rate / float(1 << 20))
        return _("%(size)s mb/s", {"size": value})
    elif rate >= (1 << 10):
        value = "%1.1f" % (rate / float(1 << 10))
        return _("%(size)s kb/s", {"size": value})
    elif rate > 0:
        value = "%1.1f" % rate
        return _("%(size)s b/s", {"size": value})
    else:
        return ""

def time(secs):
    if secs >= (60 * 60 * 24):
        t_dy = secs / (60 * 60 * 24)
        return ngettext('%(num).1f day', '%(num).1f days', t_dy, {"num": t_dy})
    if secs >= (60 * 60):
        t_hr = secs / (60 * 60)
        return ngettext('%(num).1f hr', '%(num).1f hrs', t_hr, {"num": t_hr})
    if secs >= 60:
        t_min = secs / 60
        return ngettext('%(num).1f min', '%(num).1f mins', t_min, {"num": t_min})

    return ngettext('%(num)d sec', '%(num)d secs', secs, {"num": secs})

def size(bytes):
    # when switching from the enclosure reported size to the downloader
    # reported size, it takes a while to get the new size and the downloader
    # returns -1.  the user sees the size go to -1B which is weird....
    # better to return an empty string.
    if bytes == -1 or bytes == 0:
        return ""

    # FIXME this is a repeat of util.formatSizeForUser ...  should
    # probably ditch one of them.
    if bytes >= (1 << 30):
        value = "%.1f" % (bytes / float(1 << 30))
        return _("%(size)s gb", {"size": value})
    elif bytes >= (1 << 20):
        value = "%.1f" % (bytes / float(1 << 20))
        return _("%(size)s mb", {"size": value})
    elif bytes >= (1 << 10):
        value = "%.1f" % (bytes / float(1 << 10))
        return _("%(size)s kb", {"size": value})
    else:
        return _("%(size)s b", {"size": bytes})

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

def expiration_date_short(exp_date):
    offset = exp_date - datetime.datetime.now()
    if offset.days > 0:
        return ngettext("Expires: %(count)d day",
                        "Expires: %(count)d days",
                        offset.days,
                        {"count": offset.days})
    elif offset.seconds > 3600:
        return ngettext("Expires: %(count)d hour",
                        "Expires: %(count)d hours",
                        math.ceil(offset.seconds/3600.0),
                        {"count": math.ceil(offset.seconds/3600.0)})
    else:
        return ngettext("Expires: %(count)d minute",
                        "Expires: %(count)d minutes",
                        math.ceil(offset.seconds/60.0),
                        {"count": math.ceil(offset.seconds/60.0)})

def release_date(release_date):
    if release_date > datetime.datetime.min:
        return release_date.strftime("%B %d, %Y")
    else:
        return ''

def release_date_slashes(release_date):
    if release_date > datetime.datetime.min:
        return release_date.strftime("%x")
    else:
        return ''

def duration(seconds):
    if seconds > 0:
        return time(seconds)
    else:
        return ''
