# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""``miro.displaytext`` -- Format strings to send to the user.
"""

import math
import datetime

from miro import gtcache
from miro.gtcache import gettext as _
from miro.gtcache import ngettext

LOCALE_HAS_UNIT_CONVERSIONS = True

def strftime_to_unicode(nbytes):
    """Convert the value return by strftime() to a unicode string.

    By default, it's in whatever the default codeset is.
    """
    global LOCALE_HAS_UNIT_CONVERSIONS
    if gtcache.codeset is None or not LOCALE_HAS_UNIT_CONVERSIONS:
        return nbytes
    else:
        # bug #14713: some locales don't have unit conversions
        # defined, so then decode throws an error
        try:
            return nbytes.decode(gtcache.codeset)
        except LookupError:
            LOCALE_HAS_UNIT_CONVERSIONS = False
            return nbytes

def download_rate(rate):
    if rate >= (1 << 30):
        value = "%1.1f" % (rate / float(1 << 30))
        return _("%(size)s GB/s", {"size": value})
    elif rate >= (1 << 20):
        value = "%1.1f" % (rate / float(1 << 20))
        return _("%(size)s MB/s", {"size": value})
    elif rate >= (1 << 10):
        value = "%1.1f" % (rate / float(1 << 10))
        return _("%(size)s kB/s", {"size": value})
    elif rate > 0:
        value = "%1.1f" % rate
        return _("%(size)s B/s", {"size": value})
    else:
        return ""

def short_time_string(secs):
    """Takes an integer number of seconds and returns a string
    of the form MM:SS.
    """
    try:
        return "%d:%02d" % divmod(int(round(secs)), 60)
    except TypeError:
        return "0:00"

def time_string(secs):
    if secs >= (60 * 60 * 24):
        t_dy = secs * 1.0 / (60 * 60 * 24)
        return ngettext('%(num).0f day', '%(num).0f days', int(t_dy),
                        {"num": t_dy})
    if secs >= (60 * 60):
        t_hr = secs * 1.0 / (60 * 60)
        return ngettext('%(num).0f hr', '%(num).0f hrs', int(t_hr),
                        {"num": t_hr})
    if secs >= 60:
        t_min = secs * 1.0 / 60
        return ngettext('%(num).0f min', '%(num).0f mins', int(t_min),
                        {"num": t_min})

    return ngettext('%(num)d sec', '%(num)d secs', secs, {"num": secs})

def size_string(nbytes):
    # when switching from the enclosure reported size to the
    # downloader reported size, it takes a while to get the new size
    # and the downloader returns -1.  the user sees the size go to -1B
    # which is weird....  better to return an empty string.
    if nbytes == -1 or nbytes == 0:
        return ""

    # FIXME this is a repeat of util.format_size_for_user ...  should
    # probably ditch one of them.
    if nbytes >= (1 << 30):
        value = "%.1f" % (nbytes / float(1 << 30))
        return _("%(size)s GB", {"size": value})
    elif nbytes >= (1 << 20):
        value = "%.1f" % (nbytes / float(1 << 20))
        return _("%(size)s MB", {"size": value})
    elif nbytes >= (1 << 10):
        value = "%.1f" % (nbytes / float(1 << 10))
        return _("%(size)s KB", {"size": value})
    else:
        return _("%(size)s B", {"size": nbytes})

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

def release_date(rdate):
    """Takes a date object and returns the "month day, year"
    representation.

    If the rdate is below the minimum date, then this returns an
    empty string.
    """
    if rdate is None:
        return ''
    if rdate > datetime.datetime.min:
        # figure out the date pieces, convert to unicode, then split
        # it on "::" so we can run gettext on it allowing translators
        # to reorder it.  see bug 11662.
        m, d, y = strftime_to_unicode(rdate.strftime("%B::%d::%Y")).split("::")
        return _("%(month)s %(dayofmonth)s, %(year)s",
                 {"month": m, "dayofmonth": d, "year": y})
    else:
        return ''

def release_date_slashes(rdate):
    """Takes a date object and returns the "MM/DD/YYYY"
    representation.

    If the rdate is below the minimum date, then this returns an
    empty string.
    """
    if rdate is None:
        return ''
    if rdate > datetime.datetime.min:
        # note: %x is locale-appropriate
        return strftime_to_unicode(rdate.strftime("%x"))
    else:
        return ''

def duration(seconds):
    if seconds > 0:
        return time_string(seconds)
    else:
        return ''
