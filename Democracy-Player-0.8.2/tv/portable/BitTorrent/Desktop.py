# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# written by Matt Chisholm

import os

from __init__ import get_home_dir

desktop = None

homedir = get_home_dir()
if homedir == None :
    if os.name == 'nt':
        desktop = 'C:\\'
    else:
        desktop = '/tmp/'

else:
    desktop = homedir
    if os.name in ('mac', 'posix', 'nt'):

        tmp_desktop = os.path.join(homedir, 'Desktop')
        if os.access(tmp_desktop, os.R_OK|os.W_OK):
            desktop = tmp_desktop + os.sep

        if os.name == 'nt':
            #from win32com.shell import shell, shellcon
            #desktop = shell.SHGetPathFromIDList(shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DESKTOPDIRECTORY))
            reg_desktop = None
            import _winreg as wreg
            try: 
                key = wreg.OpenKey(wreg.HKEY_CURRENT_USER,
                               r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders')
                d = wreg.QueryValueEx(key, 'Desktop')
                reg_desktop = os.path.expandvars(d, os.environ)
            except:
                pass

            if reg_desktop is not None and os.access(reg_desktop, os.R_OK|os.W_OK):
                desktop = reg_desktop
