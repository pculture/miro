import os
import sys

from glob import glob

if len(sys.argv) == 2:
    nib = "Resources/English.lproj/%s.nib" % sys.argv[1]
    if not os.path.exists(nib):
        print "Unknown nib file: %s" % nib
        sys.exit()
    else:
        nibs = [nib]
else:
    nibs = glob("Resources/English.lproj/*.nib")

for lproj in glob("Resources/*.lproj"):
    lang = os.path.basename(lproj)[:-6]
    if lang == "English":
        continue
    if os.path.exists ("Resources/%s.lproj/translated.strings" % (lang)):
        for nib in nibs:
            name = os.path.basename (nib)[:-4]
            exists = os.path.exists ("Resources/%s.lproj/%s.nib" % (lang, name))
            if exists:
                nib = "Resources/%s.lproj/temp.%s.nib" % (lang, name)
            else:
                nib = "Resources/%s.lproj/%s.nib" % (lang, name)
            os.system ("nibtool -8 Resources/English.lproj/%s.nib -d Resources/%s.lproj/translated.strings -W %s" % (name, lang, nib))
            if exists:
                os.system ("mv Resources/%s.lproj/temp.%s.nib/* Resources/%s.lproj/%s.nib/" % (lang, name, lang, name))
                os.system ("rmdir Resources/%s.lproj/temp.%s.nib" % (lang, name))
