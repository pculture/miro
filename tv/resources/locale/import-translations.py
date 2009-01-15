#!/usr/bin/env python
"""
This script is for importing a Launchpad export of .po files.
It handles both the "full export" case and individual .po files.
It:

 * fixes the filenames to what Miro uses,
 * fixes some bugs we've seen in some of the translations, and
 * calls msgfmt on the .po files creating .mo files

It's just a utility script.  If you find it needs additional bits,
let us know.
"""

import glob
import os.path
import os

def get_files():
    return [mem for mem in os.listdir(".") if mem.endswith(".po")]

def fix_names():
    files = get_files()
    for pofile in files:
        newfilename = pofile
        for repl in ["democracyplayer_", "democracyplayer-"]:
            newfilename = newfilename.replace(repl, "")
        if newfilename != pofile:
             os.system("mv %s %s" % (pofile, newfilename))

def fix_ro_plurals():
    bad_str = '"Plural-Forms: nplurals=3; plural=((n == 1 ? 0: (((n %\\n"\n"100 > 19) || ((n % 100 == 0) && (n != 0))) ? 2: 1)));\\n"'

    good_str = '"Plural-Forms: nplurals=3; plural=((n == 1 ? 0: (((n % 100 > 19) || ((n % 100 == 0) && (n != 0))) ? 2: 1)));\\n"'
    ro_path = os.path.normpath(os.path.join(__file__, '..', 'ro.po'))
    content = open(ro_path).read()
    if bad_str in content:
        print 'fixing ro.po'
        f = open(ro_path, 'wt')
        f.write(content.replace(bad_str, good_str))
        f.close()

def fix_pound_pipe():
    files = get_files()
    for pofile in files:
        f = open(pofile, "r")
        lines = [line for line in f.readlines() if not line.startswith("#|")]
        f.close()
        f = open(pofile, "w")
        f.write("".join(lines))
        f.close()

def build_catalogs():
    files = get_files()
    for pofile in files:
        mofile = "%s.mo" % pofile[:-3]
        os.system("msgfmt %s -o %s" % (pofile, mofile))

if __name__ == "__main__":
    print "FIXING NAMES...."
    fix_names()
    print "FIXING #| issues...."
    fix_pound_pipe()
    print "FIXING RO PLURALS...."
    fix_ro_plurals()
    print "BUILDING .mo FILES...."
    build_catalogs()
