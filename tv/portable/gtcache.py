# Caching gettext functions

import gettext as _gt
import locale
import config
import prefs
import platformutils
import os

_gtcache = None

def init():
    global _gtcache
    _gtcache = {}
    if not platformutils.localeInitialized:
        raise Exception, "locale not initialized"
    locale.setlocale(locale.LC_ALL, '')

    _gt.bindtextdomain("democracyplayer", config.get(prefs.GETTEXT_PATHNAME))
    _gt.textdomain("democracyplayer")
    _gt.bind_textdomain_codeset("democracyplayer","UTF-8")

def gettext(text):
    text = text.encode('utf-8')
    try:
        return _gtcache[text]
    except KeyError:
        out = _gt.gettext(text).decode('utf-8')
        _gtcache[text] = out
        return out
    except TypeError:
        print "DTV: WARNING: gettext not initialized for string \"%s\"" % text
        import traceback
        traceback.print_stack()
        return text

def ngettext(text1, text2, count):
    text1 = text1.encode('utf-8')
    text2 = text2.encode('utf-8')
    try:
        return _gtcache[(text1,text2,count)]
    except:
        out = _gt.ngettext(text1, text2, count).decode('utf-8')
        _gtcache[(text1,text2,count)] = out
        return out
