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


# Let's use xgettext for this since it supports string tables.
langs = (("fr", "French"),
         ("es", "Spanish"),
         )
for lang in langs:
    try:
        os.makedirs ("../../platform/osx/Resources/%s.lproj" % (lang[1],))
    except:
        pass
    # The perl statement removes po entries that have plurals in them since xgettext gives an error on those when writing a stringtable.
    os.system ( "cat %s.po | perl -e '$/=\"\"; while (<>) {print if !/msgid_plural/;}' | xgettext --force -o ../../platform/osx/Resources/%s.lproj/translated.strings --stringtable-output - -L PO" % (lang[0], lang[1]))
