# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

"""Code to valitade the DTD files we use for democracy.  This is very
important, since if the xulrunner can't parse the dtds then the program won't
start.  See #3579.

NOTE: This isn't real DTD valitation, it's stricter than the w3c spec.  My
reasoning was that it's better to err on the safe side.
"""

from glob import glob
import os
import re

space = r'\s+'
reference = r'(&#[0-9]+;)|(&#x[0-9a-fA-F]+)|(&quot;)|(&copy;)|(&apos;)'
entity_value = r'"(([^%&"\']|' + reference+ r')*)"'
name = r'[a-zA-Z_:][a-zA-Z_:0-9\-\.]*'
entity_start = r'<!ENTITY'
entity_end = r'\s*>'
entity = entity_start + space + name + space + entity_value + entity_end
entity_re = re.compile(entity)

def explain_error(string):
    if not re.match(entity_start + space, string):
        return "Invalid start"
    if not re.match(entity_start + space + name + space, string):
        return "Invalid name"
    if not re.match(entity_start + space + name + space + entity_value + space, string):
        return "Invalid entity data"
    else:
        return "Invalid ending"

def check_dtd(path):
    content = open(path).read().lstrip()
    while content:
        m = entity_re.match(content)
        if m is None:
            string = content[:content.find(">")+1]
            raise ValueError("Error validating entity: %r\n%s\nin file: %s" \
                    % (string, explain_error(content), path))
        else:
            string = content[:content.find(">")+1]
            # This entity is illegal, so we shouldn't use it
            if m.group(1).find('&copy;') != -1:
                raise ValueError("Error validating entity: %r\n%s\nin file: %s" \
                                 % (string, explain_error(content), path))
            content = content[m.end():].lstrip()

def check_dtds(locale_dir):
    for fname in os.listdir(locale_dir):
        subdir = os.path.join(locale_dir, fname)
        if fname != '.svn' and os.path.isdir(subdir):
            for dtd in glob(os.path.join(subdir, "*.dtd")):
                check_dtd(dtd)
