# This shell script now requires a modified intltool.

intltool-extract --type=gettext/glade ../../platform/gtk-x11/glade/democracy.glade
for dtd in ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template; do
    intltool-extract --type=gettext/quoted $dtd
done
xgettext -k_ -kN_ -o messages.pot `find ../../ -name '*.py' -and -not -path '*.svn*' -and -not -path '*build*' -and -not -path '*dist*'` ../../platform/gtk-x11/glade/democracy.glade.h ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.h ../../platform/windows-xul/xul/chrome/locale/en-US/*.dtd.template.h
