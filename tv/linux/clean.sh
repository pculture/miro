#!/bin/bash

rm -rf build dist
rm -rf miro.1.gz miro.real.1.gz
rm -f plat/xlibhelper.c
rm -f ../lib/frontends/widgets/gtk/pygtkhacks.c
rm -f ../lib/frontends/widgets/gtk/webkitgtkhacks.c
rm -f ../lib/frontends/widgets/infolist/infolist.c
rm -rf tmp
rm -f plat/frontends/widgets/windowcreator.cpp
rm -f plat/frontends/widgets/pluginsdir.cpp
rm -f plat/frontends/widgets/mozprompt.c
rm -f plat/frontends/widgets/mozprompt.h
rm -f plat/frontends/widgets/httpobserver.c

