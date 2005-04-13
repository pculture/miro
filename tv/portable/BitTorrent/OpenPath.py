# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

import os

can_open_files = False
posix_browsers = ('gnome-open','konqueror',) #gmc, gentoo only work on dirs
default_posix_browser = ''

def openpath_nt(path):
    os.startfile(path)

def openpath_mac(path):
    # BUG: this is untested
    os.spawnlp(os.P_NOWAIT, 'open', 'open', path)

def openpath_posix(path):
    if default_posix_browser:
        os.spawnlp(os.P_NOWAIT, default_posix_browser,
                   default_posix_browser, path)

def openpath(path):
    pass

def opendir(path):
    if os.path.isdir(path):
        openpath(path)

if os.name == 'nt':
    can_open_files = True
    openpath = openpath_nt
elif os.name == 'mac':
    can_open_files = True
    openpath = openpath_mac
elif os.name == 'posix':
    for b in posix_browsers:
        if os.system('which %s >/dev/null'%b) == 0:
            can_open_files = True
            default_posix_browser = b
            openpath = openpath_posix
            break

