#!/bin/sh

xgettext -k_ -o messages.pot `find ../../ -name '*.py' -and -not -path '*testdata*' -and -not -path '*.svn*' -and -not -path '*build*' -and -not -path '*dist*' -and -not -path '*feedparser.py' -and -not -path '*portable/test/*'`
