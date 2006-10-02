# Caching gettext functions

import gettext as _gt
import locale
import config
import prefs

_gtcache = {}

locale.setlocale(locale.LC_ALL, '')
_gt.bindtextdomain("democracyplayer", config.get(prefs.GETTEXT_PATHNAME))
_gt.textdomain("democracyplayer")
_gt.bind_textdomain_codeset("democracyplayer","UTF-8")


def gettext(text):
    try:
        return _gtcache[text]
    except:
        out = _gt.gettext(text).decode('utf-8')
        _gtcache[text] = out
        return out

def ngettext(text1, text2, count):
    try:
        return _gtcache[(text1,text2,count)]
    except:
        out = _gt.ngettext(text1, text2, count).decode('utf-8')
        _gtcache[(text1,text2,count)] = out
        return out
