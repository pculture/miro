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

"""miro_urlparse.py -- Replacement for urlparse than fixes #13210."""

import urlparse as sys_urlparse

def _fix_returned_list(url, retval):
    # this is the main work, we check that the return value components have
    # the same type as the url
    if isinstance(url, unicode):
        return map(unicode, retval)
    elif isinstance(url, str):
        return map(str, retval)
    return retval

def _fix_returned_string(url, retval):
    if isinstance(url, unicode):
        return unicode(retval)
    elif isinstance(url, str):
        return str(retval)
    return retval

def urlparse(url, default_scheme="", allow_fragments=True):
    return _fix_returned_list(url, sys_urlparse.urlparse(url, default_scheme,
        allow_fragments))

def urlsplit(url, default_scheme="", allow_fragments=True):
    return _fix_returned_list(url, sys_urlparse.urlsplit(url, default_scheme,
        allow_fragments))

def urljoin(base, url, allow_fragments=True):
    return _fix_returned_string(url, sys_urlparse.urljoin(base, url,
        allow_fragments))

def apply_monkey_patch():
    # hack the sys.modules dict to use this module instead of the system
    # urlparse (Note that we've already imported the system urlparse at the
    # top of this module).
    from miro.plat import miro_urlparse
    import sys
    sys.modules['urlparse'] = miro_urlparse
