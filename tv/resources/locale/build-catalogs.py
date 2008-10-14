import glob
import os.path
import os

os.system("python fix-ro-plurals.py")

for pofile in glob.glob ("*.po"):
    lang = pofile[:-3]
    mofile = os.path.join ("%s.mo" % lang)
    os.system("msgfmt %s -o %s" % (pofile, mofile))
