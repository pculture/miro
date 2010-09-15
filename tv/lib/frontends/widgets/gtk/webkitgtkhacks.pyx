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

"""webkitgtkhacks.pyx

Webkit code that can't be done with the python bindings.
"""

cdef extern from "gtk/gtk.h":
    ctypedef void * gpointer
    ctypedef unsigned int gboolean
    cdef void g_object_unref(gpointer object)

cdef extern from "libsoup/soup.h":
    ctypedef void* SoupSession
    ctypedef void* SoupSessionFeature
    ctypedef void* SoupCookieJarText

    SoupCookieJarText* soup_cookie_jar_text_new(char* filename,
            gboolean read_only)
    void soup_session_add_feature(SoupSession* session,
            SoupSessionFeature* feature)

cdef extern from "webkit/webkit.h":
    cdef SoupSession* webkit_get_default_session()

def setup_cookie_storage(object filename):
    cdef SoupSession* session
    cdef SoupCookieJarText* cookie_jar

    session = webkit_get_default_session()
    if not session:
        raise AssertionError("webkit_get_default_session() returned NULL")
    cookie_jar = soup_cookie_jar_text_new(filename, 0)
    if not cookie_jar:
        raise AssertionError("soup_cookie_jar_text_new() returned NULL")
    soup_session_add_feature (session, <SoupSessionFeature*> cookie_jar)
    g_object_unref(cookie_jar)
