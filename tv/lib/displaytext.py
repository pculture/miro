# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import datetime

from miro import gtcache
from miro.gtcache import gettext as _
from miro.gtcache import ngettext

LOCALE_HAS_UNIT_CONVERSIONS = True

def strftime_to_unicode(nbytes):
    """Convert the value return by strftime() to a unicode string.

    By default, it's in whatever the default codeset is.  If we can't find a
    codeset then assume utf-8 to give us a base to always return unicode.
    """
    global LOCALE_HAS_UNIT_CONVERSIONS
    if gtcache.codeset is None or not LOCALE_HAS_UNIT_CONVERSIONS:
        return nbytes.decode('utf-8', 'replace')
    else:
        # bug #14713: some locales don't have unit conversions
        # defined, so then decode throws an error
        try:
            return nbytes.decode(gtcache.codeset)
        except LookupError:
            LOCALE_HAS_UNIT_CONVERSIONS = False
            return nbytes.decode('utf-8', 'replace')

def download_rate(rate):
    if rate is None:
        return ""
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
        return ""

def time_string(secs):
    if secs >= (60 * 60 * 24):
        return days_string(secs)
    if secs >= (60 * 60):
        return hrs_string(secs)
    if secs >= 60:
        return mins_string(secs)
    return secs_string(secs)

def days_string(secs):
    t_dy = int(round(secs / (60.0 * 60.0 * 24.0)))
    return ngettext('%(num)d day', '%(num)d days', t_dy,
                    {"num": t_dy})

def hrs_string(secs):
    t_hr = int(round(secs / (60.0 * 60.0)))
    return ngettext('%(num)d hr', '%(num)d hrs', t_hr,
                    {"num": t_hr})

def mins_string(secs):
    t_min = int(round(secs / 60.0))
    return ngettext('%(num)d min', '%(num)d mins', t_min,
                    {"num": t_min})

def secs_string(secs):
    return ngettext('%(num)d sec', '%(num)d secs', secs, {"num": secs})

def time_string_0_blank(secs):
    if secs <= 0:
        return ''
    else:
        return time_string(secs)

def size_string(nbytes):
    if nbytes is None:
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
        hours = int(round(offset.seconds / 3600.0))
        return ngettext("Expires in %(count)d hour",
                        "Expires in %(count)d hours",
                        hours,
                        {"count": hours})
    else:
        minutes = int(round(offset.seconds / 60.0))
        return ngettext("Expires in %(count)d minute",
                        "Expires in %(count)d minutes",
                        minutes,
                        {"count": minutes})

def expiration_date_short(exp_date):
    offset = exp_date - datetime.datetime.now()
    if offset.days > 0:
        return ngettext("Expires: %(count)d day",
                        "Expires: %(count)d days",
                        offset.days,
                        {"count": offset.days})
    elif offset.seconds > 3600:
        hours = int(round(offset.seconds / 3600.0))
        return ngettext("Expires: %(count)d hour",
                        "Expires: %(count)d hours",
                        hours,
                        {"count": hours})
    else:
        minutes = int(round(offset.seconds / 60.0))
        return ngettext("Expires: %(count)d minute",
                        "Expires: %(count)d minutes",
                        minutes,
                        {"count": minutes})

def date(rdate):
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

def date_slashes(rdate):
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

def duration(secs):
    if secs >= 60:
        return mins_string(secs)
    elif secs > 0:
        return secs_string(secs)
    else:
        return ''

def integer(num):
    if num < 0:
        return ""
    try:
        num = int(num)
    except (ValueError, TypeError):
        return ""
    return str(num)
