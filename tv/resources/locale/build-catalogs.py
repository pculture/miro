import glob
import os.path
import os

os.system("python fix-ro-plurals.py")

for pofile in glob.glob ("*.po"):
    lang = pofile[:-3]
    mofile = os.path.join ("%s.mo" % lang)
    os.system ("msgfmt %s -o %s" % (pofile, mofile))

for dtd in glob.glob ("../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template"):
    dtd = os.path.basename (dtd)
    os.system ("(cd ../../platform/windows-xul/xul/chrome/locale/; intltool-merge --quoted-style -m ../../../../../resources/locale/ en-US/%s %s)" % (dtd, dtd))
    os.system ("(cd ../../platform/windows-xul/xul/chrome/locale/; perl -pi -e 's/\\\\\\\"/&quot;/g' */%s)" % (dtd,))


# Let's use xgettext for this since it supports string tables.
langs = (
         ("ar", "Arabic"),
         ("bg", "Bulgarian"),
         ("br", "Breton"),
         ("bs", "Bosnian"),
         ("ca", "Catalan"),
         ("cs", "Czech"),
         ("csb", "Kashubian"),
         ("cy", "Welsh"),
         ("da", "Danish"),
         ("de", "German"),
         ("el", "Greek"),
         ("en_AU", "English_Australian"),
         ("en_GB", "English_British"),
         ("eo", "Esperanto"),
         ("es", "Spanish"),
         ("et", "Estonian"),
         ("eu", "Basque"),
         ("fa", "Persian"),
         ("fi", "Finnish"),
         ("fil", "Filipino"),
         ("fr", "French"),
         ("fo", "Faroese"),
         ("fy", "Frisian"),
         ("gl", "Gallegan"),
         ("gu", "Gujarati"),
         ("he", "Hebrew"),
         ("hi", "Hindi"),
         ("hr", "Croatian"),
         ("hu", "Hungarian"),
         ("id", "Indonesian"),
         ("is", "Icelandic"),
         ("it", "Italian"),
         ("ja", "Japanese"),
         ("ka", "Georgian"),
         ("ko", "Korean"),
         ("ku", "Kurdish"),
         ("lt", "Lithuanian"),
         ("lv", "Latvian"),
         ("mk", "Macedonian"),
         ("ml", "Malayalam"),
         ("mr", "Marathi"),
         ("ms", "Malay"),
         ("nb", "Norwegian"),
         ("nds", "German_Low"),
         ("ne", "Nepali"),
         ("nl", "Dutch"),
         ("nn", "Norwegian_Nynorsk"),
         ("pa", "Punjabi"),
         ("pl", "Polish"),
         ("pt", "Portuguese"),
         ("pt_BR", "Portuguese_Brazil"),
         ("ro", "Romanian"),
         ("ru", "Russian"),
         ("si", "Sinhalese"),
         ("sk", "Slovak"),
         ("sl", "Slovenian"),
         ("sq", "Albanian"),
         ("sr", "Serbian"),
         ("sv", "Swedish"),
         ("ta", "Tamil"),
         ("te", "Telugu"),
         ("th", "Thai"),
         ("tl", "Tagalog"),
         ("tr", "Turkish"),
         ("uk", "Ukranian"),
         ("vi", "Vietnamese"),
         ("zh_CN", "Chinese_Simplified"),
         ("zh_HK", "Chinese_HK"),
         ("zh_TW", "Chinese_Traditional"),
         )
for lang in langs:
    try:
        os.makedirs ("../../platform/osx/Resources/%s.lproj" % (lang[1],))
    except Exception, e:
        print "Exception thrown making %s lproj dir: %s" % (lang, repr(e))
        pass

    # The perl statement removes po entries that have plurals in them since xgettext gives an error on those when writing a stringtable.
    os.system ( "cat %s.po | perl -e '$/=\"\"; while (<>) {print if !/msgid_plural/;}' | xgettext --force -o ../../platform/osx/Resources/%s.lproj/translated.strings --stringtable-output - -L PO" % (lang[0], lang[1]))
