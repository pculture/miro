# Caching gettext functions

import gettext as _gt
import locale
import config
import prefs
import os

_gtcache = {}

def init():
    locale.setlocale(locale.LC_ALL, '')

    _gt.bindtextdomain("democracyplayer", config.get(prefs.GETTEXT_PATHNAME))
    _gt.textdomain("democracyplayer")
    _gt.bind_textdomain_codeset("democracyplayer","UTF-8")

# Hack to delay initializing gettext in the downloader until it can
# get config information
#
# See corresponding hack in Democracy_Downloader.py
try:
    os.environ['DEMOCRACY_DOWNLOADER_PORT']
except:
    init()

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
