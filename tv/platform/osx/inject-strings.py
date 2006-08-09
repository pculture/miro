from glob import glob
import os
for lproj in glob("*.lproj"):
    lang = os.path.basename(lproj)[:-6]
    if lang == "English":
	continue
    if os.path.exists ("%s.lproj/translated.strings" % (lang)):
	for nib in glob("English.lproj/*.nib"):
	    name = os.path.basename (nib)[:-4]
	    exists = os.path.exists ("%s.lproj/%s.nib" % (lang, name))
	    if exists:
		nib = "%s.lproj/temp.%s.nib" % (lang, name)
	    else:
		nib = "%s.lproj/%s.nib" % (lang, name)
	    os.system ("nibtool -8 English.lproj/%s.nib -d %s.lproj/translated.strings -W %s" % (name, lang, nib))
	    if exists:
		os.system ("mv %s.lproj/temp.%s.nib/* %s.lproj/%s.nib/" % (lang, name, lang, name))
		os.system ("rmdir %s.lproj/temp.%s.nib" % (lang, name))
