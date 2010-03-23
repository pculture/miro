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

"""``miro.gtcache`` -- Caching gettext functions.
"""

import os
import gettext as _gt
import locale
from miro import config
from miro import prefs
import miro.plat.utils

_gtcache = None
codeset = None # The default codeset of our locale (always lower case)

def get_languages():
    from miro import iso_639
    
    lang_paths = []

    for path, dirs, files in os.walk(config.get(prefs.GETTEXT_PATHNAME)):
        if "miro.mo" in files:
            lang_paths.append(path)

    codes = [path.split(os.sep)[-2] for path in lang_paths]
    langs = []
    for i, code in enumerate(codes):
        if "_" in code:
            code, country = code.split("_")
            country = " (%s)" % country
        else:
            country = ""

        lang = iso_639.find(code)
        if lang is None:
            lang = code
        else:
            lang = lang['name'] + country
        langs.append((code, lang))
    langs.sort(lambda x, y: cmp(x[1], y[1]))

    langs.insert(0, ("en", "English"))
    
    return langs

def init():
    import logging
    global _gtcache
    global codeset
    _gtcache = {}
    if not miro.plat.utils.locale_initialized():
        raise Exception, "locale not initialized"

    language = config.get(prefs.LANGUAGE)

    if language != "system":
        import os
        os.environ["LANGUAGE"] = language

    # try to set the locale to the platform default, but if that fails
    # log a message and set it to C.
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        print "gtcache.init: setlocale failed.  setting locale to 'C'"
        locale.setlocale(locale.LC_ALL, 'C')

    # try to get the locale which might fail despite the above.  see bug #11783.
    try:
        codeset = locale.getlocale()[1]
    except ValueError:
        print "gtcache.init: getlocale failed.  setting locale to 'C'"
        locale.setlocale(locale.LC_ALL, "C")
        codeset = locale.getlocale()[1]

    if codeset is not None:
        codeset = codeset.lower()

    _gt.bindtextdomain("miro", config.get(prefs.GETTEXT_PATHNAME))
    _gt.textdomain("miro")
    _gt.bind_textdomain_codeset("miro", "UTF-8")

def declarify(text):
    """Takes the return from a gettext call, and "declarifies" it.  If the
    item has | symbols in it, then this splits the string on | and returns
    the last string.  If the item has no | symbols in it, then it returns
    the string.

    >>> declarify("foo")
    'foo'
    >>> declarify("View|All")
    'All'

    Returns a unicode string.
    """
    if "|" in text:
        return text.split("|")[-1]
    return text

def gettext(text, values=None):
    """Returns the translated form of the given text.  If values are provided,
    expands the string with the given values.

    In the case where the translated string is improperly formed and throws
    a ValueError when expanded, this caches and returns the original text.
    This reduces the likelihood that Miro will throw an error and stop
    functioning with bad translated strings.

    For example, if the string is::

        "%(countfiles) fichiers analyses"
                     ^^^

    the d is missing.

    .. Note::

       This converts unicode strings to strings in utf-8 encoding
       before translating.  This definitely slows things down, so if
       you don't need unicode characters, use a string and not a
       unicode.

    Returns a unicode string.
    """
    text = text.encode('utf-8')
    try:
        s = _gtcache[text]

    except KeyError:
        s = _gt.gettext(text).decode('utf-8')
        _gtcache[text] = s

    except TypeError:
        print "gtcache.gettext: not initialized for string \"%s\"" % text
        # import traceback
        # traceback.print_stack()
        return text

    try:
        if values:
            s = s % values
        return s

    except ValueError:
        import logging
        logging.warn("gtcache.gettext: translation has bad formatting characters.  returning english form.  '%s'", text)
        _gtcache[text] = text
        return text % values

def ngettext(text1, text2, count, values=None):
    """Given two strings and a count.

    text1
        the singular form of the string to be translated
    text2
        the plural form of the string to be translated
    count
        the number of things involved
    values
        the dict of values to expand the string with

    See Python ``gettext.ngettext`` documentation and the GNU gettext
    documentation for more details.

    http://www.gnu.org/software/gettext/manual/gettext.html#Plural-forms

    Returns a unicode string.
    """
    text1 = text1.encode('utf-8')
    text2 = text2.encode('utf-8')

    s = _gt.ngettext(text1, text2, count).decode('utf-8')
    try:
        if values:
            s = s % values
        return s

    except ValueError:
        import logging
        logging.warn("gtcache.ngettext: translation has bad formatting characters.  returning english form.  '%s'", text1)
        if count == 1:
            return text1 % values
        else:
            return text2 % values
