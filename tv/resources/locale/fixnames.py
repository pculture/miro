# Launchpad sends us files with names like ``democracyplayer-nl.po`` and this
# script strips the ``democracyplayer-`` bit off.
#
# Syntax: ./fixnames.py

import os

files = [ mem for mem in os.listdir(".") if mem.endswith(".po") ]
for pofile in files:
    if pofile.startswith("democracyplayer-"):
         os.system("mv %s %s" % (pofile, pofile.replace("democracyplayer-", "")))
