# Caching gettext functions

import gettext as _gt

_gtcache = {}

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
