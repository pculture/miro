intltool-extract --type=gettext/glade ../../platform/gtk-x11/glade/democracy.glade
xgettext -k_ -kN_ -o messages.pot `find ../../ -name '*.py' -and -not -path '*.svn*' -and -not -path '*build*' -and -not -path '*dist*'` ../../platform/gtk-x11/glade/democracy.glade.h
