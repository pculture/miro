# This shell script now requires a modified intltool.

intltool-extract --type=gettext/glade ../../platform/gtk-x11/glade/miro.glade
for dtd in ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template; do
    intltool-extract --type=gettext/quoted $dtd
done

# Strings has to come first because the code that parses strings doesn't handle multiple references to the same string, while the rest of the xgettext parsers do.

xgettext -k_ -kN_ -o messages.pot ../../platform/osx/Resources/English.lproj/*.strings `find ../../ -name '*.py' -and -not -path '*.svn*' -and -not -path '*build*' -and -not -path '*dist*' -and -not -path '*feedparser.py' -and -not -path '*portable/test/*'` ../../platform/gtk-x11/glade/miro.glade.h ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template.h

