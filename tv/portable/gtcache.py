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

# Caching gettext functions

import gettext as _gt
import locale
from miro import config
from miro import prefs
import miro.plat.utils

_gtcache = None

def init():
    global _gtcache
    _gtcache = {}
    if not miro.plat.utils.localeInitialized:
        raise Exception, "locale not initialized"

    # try to set the locale to the platform default, but if that fails
    # log a message and set it to C.
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        import logging
	logging.warn("gtcache.init: setlocale failed.  setting locale to 'C'")
        locale.setlocale(locale.LC_ALL, 'C')

    _gt.bindtextdomain("miro", config.get(prefs.GETTEXT_PATHNAME))
    _gt.textdomain("miro")
    _gt.bind_textdomain_codeset("miro", "UTF-8")

def gettext(text):
    """Given a string, returns the translated form of that string.

    Note that this converts unicode strings to strings in utf-8 encoding
    before translating.  This definitely slows things down, so if you
    don't need unicode characters, use a string and not a unicode.

    Returns a unicode string.
    """
    text = text.encode('utf-8')
    try:
        return _gtcache[text]
    except KeyError:
        out = _gt.gettext(text).decode('utf-8')
        _gtcache[text] = out
        return out
    except TypeError:
        print "MIRO: WARNING: gettext not initialized for string \"%s\"" % text
        import traceback
        traceback.print_stack()
        return text

def ngettext(text1, text2, count):
    """Given two strings and a count.

    text1 - the singular form of the string to be translated
    text2 - the plural form of the string to be translated
    count - the number of things involved

    See Python ``gettext.ngettext`` documentation and the GNU gettext
    documentation for more details.

    http://www.gnu.org/software/gettext/manual/gettext.html#Plural-forms

    Returns a unicode string.
    """
    text1 = text1.encode('utf-8')
    text2 = text2.encode('utf-8')
    try:
        return _gtcache[(text1, text2, count)]
    except:
        out = _gt.ngettext(text1, text2, count).decode('utf-8')
        _gtcache[(text1, text2, count)] = out
        return out
