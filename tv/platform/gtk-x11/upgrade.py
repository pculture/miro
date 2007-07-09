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

import os
import shutil
import resources

def upgrade():
    src = os.path.expanduser('~/.democracy')
    dst = os.path.expanduser('~/.miro')
    if os.path.isdir(src) and not os.path.exists(dst):
        shutil.move(src, dst)
        shutil.rmtree(os.path.join(dst, "icon-cache"), True)

    config_home = os.environ.get ('XDG_CONFIG_HOME',
                                  '~/.config')
    config_home = os.path.expanduser (config_home)
    autostart_dir = os.path.join (config_home, "autostart")
    old_file = os.path.join (autostart_dir, "democracyplayer.desktop")
    destination = os.path.join (autostart_dir, "miro.desktop")
    if os.path.exists(old_file):
        if not os.path.exists(destination):
            try:
                os.makedirs(autostart_dir)
            except:
                pass
            try:
                shutil.copy (resources.sharePath('applications/miro.desktop'), destination)
            except:
                pass
            try: 
                os.remove (old_file)
            except:
                pass
