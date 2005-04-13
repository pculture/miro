# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Bill Bumgarner and Bram Cohen

import sys
from types import *
from cStringIO import StringIO

from BitTorrent.obsoletepythonsupport import *

from BitTorrent import BTFailure, is_frozen_exe
if is_frozen_exe:
    from BitTorrent.GUI import HelpWindow

def makeHelp(uiname, defaults):
    ret = ''
    ret += ("Usage: %s " % uiname)
    if uiname.startswith('btlaunchmany'):
        ret += "[OPTIONS] [TORRENTDIRECTORY]\n\n"
        ret += "If a non-option argument is present it's taken as the value\n"\
              "of the torrent_dir option.\n"
    elif uiname == 'btdownloadgui':
        ret += "[OPTIONS] [TORRENTFILES]\n"
    elif uiname.startswith('btdownload'):
        ret += "[OPTIONS] [TORRENTFILE]\n"
    elif uiname == 'btmaketorrent':
        ret += "[OPTION] TRACKER_URL FILE [FILE]\n"
    ret += '\n'
    ret += 'arguments are -\n' + formatDefinitions(defaults, 80)
    return ret

def printHelp(uiname, defaults):
    if is_frozen_exe:
        HelpWindow(None, makeHelp(uiname, defaults))
    else:
        print makeHelp(uiname, defaults)

def formatDefinitions(options, COLS):
    s = StringIO()
    indent = " " * 10
    width = COLS - 11

    if width < 15:
        width = COLS - 2
        indent = " "

    for (longname, default, doc) in options:
        if doc == '':
            continue
        s.write('--' + longname + ' <arg>\n')
        if default is not None:
            doc += ' (defaults to ' + repr(default) + ')'
        i = 0
        for word in doc.split():
            if i == 0:
                s.write(indent + word)
                i = len(word)
            elif i + len(word) >= width:
                s.write('\n' + indent + word)
                i = len(word)
            else:
                s.write(' ' + word)
                i += len(word) + 1
        s.write('\n\n')
    return s.getvalue()

def usage(str):
    raise BTFailure(str)

def format_key(key):
    if len(key) == 1:
        return '-%s'%key
    else:
        return '--%s'%key

def parseargs(argv, options, minargs = None, maxargs = None, presets = None):
    config = {}
    for option in options:
        longname, default, doc = option
        config[longname] = default
    args = []
    pos = 0
    if presets is None:
        presets = {}
    else:
        presets = presets.copy()
    while pos < len(argv):
        if argv[pos][:1] != '-':             # not a cmdline option
            args.append(argv[pos])
            pos += 1
        else:
            key, value = None, None
            if argv[pos][:2] == '--':        # --aaa 1
                if pos == len(argv) - 1:
                    usage('parameter passed in at end with no value')
                key, value = argv[pos][2:], argv[pos+1]
                pos += 2
            elif argv[pos][:1] == '-':
                key = argv[pos][1:2]
                if len(argv[pos]) > 2:       # -a1
                    value = argv[pos][2:]
                    pos += 1
                else:                        # -a 1
                    if pos == len(argv) - 1:
                        usage('parameter passed in at end with no value')
                    value = argv[pos+1]
                    pos += 2
            else:
                raise BTFailure('command line parsing failed at '+argv[pos])

            presets[key] = value
    parse_options(config, presets)
    config.update(presets)
    for key, value in config.items():
        if value is None:
            usage("Option %s is required." % format_key(key))
    if minargs is not None and len(args) < minargs:
        usage("Must supply at least %d args." % minargs)
    if maxargs is not None and len(args) > maxargs:
        usage("Too many args - %d max." % maxargs)
    return (config, args)

def parse_options(defaults, newvalues):
    for key, value in newvalues.iteritems():
        if not defaults.has_key(key):
            raise BTFailure('unknown key ' + format_key(key))
        try:
            t = type(defaults[key])
            if t is NoneType or t is StringType:
                newvalues[key] = value
            elif t in (IntType, LongType):
                newvalues[key] = int(value)
            elif t is FloatType:
                newvalues[key] = float(value)
            else:
                assert False
        except ValueError, e:
            raise BTFailure('wrong format of %s - %s' % (format_key(key), str(e)))
