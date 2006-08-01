# Caching gettext functions

import gettext as _gt

_gtcache = {}

def gettext(text):
    try:
        return _gtcache[text]
    except:
        out = _gt.gettext(text)
        _gtcache[text] = out
        return out

def ngettext(text1, text2, count):
    try:
        return _gtcache[(text1,text2,count)]
    except:
        out = _gt.ngettext(text1, text2, count)
        _gtcache[(text1,text2,count)] = out
        return out
