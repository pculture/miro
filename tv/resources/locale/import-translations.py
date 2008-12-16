#!/usr/bin/env python

import glob
import os.path
import os

def fix_names():
    files = [ mem for mem in os.listdir(".") if mem.endswith(".po") ]
    for pofile in files:
        if pofile.startswith("democracyplayer-"):
             os.system("mv %s %s" % (pofile, pofile.replace("democracyplayer-", "")))

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

def build_catalogs():
    for pofile in glob.glob ("*.po"):
        lang = pofile[:-3]
        mofile = os.path.join ("%s.mo" % lang)
        os.system("msgfmt %s -o %s" % (pofile, mofile))

if __name__ == "__main__":
    print "FIXING NAMES...."
    fix_names()
    print "FIXING RO PLURALS...."
    fix_ro_plurals()
    print "BUILDING .mo FILES...."
    build_catalogs()
