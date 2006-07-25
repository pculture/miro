import glob
import os.path
import os

for pofile in glob.glob ("*.po"):
    lang = pofile[:-3]
    mofile = os.path.join ("%s.mo" % lang)
    os.system ("msgfmt %s -o %s" % (pofile, mofile))

for dtd in glob.glob ("../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd") + glob.glob ("../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template"):
    dtd = os.path.basename (dtd)
    os.system ("(cd ../../platform/windows-xul/xul/chrome/locale/; intltool-merge --quoted-style -m ../../../../../resources/locale/ en-US/%s %s)" % (dtd, dtd))
