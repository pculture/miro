# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import os
import shutil
from miro.plat import resources
import gconf

def upgrade():
    # dot directory
    src = os.path.expanduser('~/.democracy')
    dst = os.path.expanduser('~/.miro')
    if os.path.isdir(src) and not os.path.exists(dst):
        shutil.move(src, dst)
        shutil.rmtree(os.path.join(dst, "icon-cache"), True)

    # autostart file
    if "KDE_FULL_SESSION" in os.environ:
        if os.environ.get("KDE_SESSION_VERSION") == "4":
            autostart_dir = "~/.kde/share/autostart"
        else:
            autostart_dir = "~/.kde/Autostart"
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
        autostart_dir = os.path.join(config_home, "autostart")

    autostart_dir = os.path.expanduser(autostart_dir)

    old_file = os.path.join(autostart_dir, "democracyplayer.desktop")
    destination = os.path.join(autostart_dir, "miro.desktop")
    if os.path.exists(old_file):
        if not os.path.exists(destination):
            try:
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                shutil.copy(resources.share_path('applications/miro.desktop'), destination)
                os.remove(old_file)
            except OSError:
                pass

    # gconf settings
    client = gconf.client_get_default()

    def _copy_gconf(src, dst):
        for entry in client.all_entries(src):
            entry_dst = dst + '/' + entry.key.split('/')[-1]
            client.set(entry_dst, entry.value)
        for subdir in client.all_dirs(src):
            subdir_dst = dst + '/' + subdir.split('/')[-1]
            _copy_gconf(subdir, subdir_dst)

    if client.dir_exists("/apps/democracy/player") and not client.dir_exists("/apps/miro"):
        _copy_gconf("/apps/democracy/player", "/apps/miro")
        client.recursive_unset("/apps/democracy", 1)
        if client.get("/apps/miro/MoviesDirectory") is None:
            value = os.path.expanduser('~/Movies/Democracy')
            client.set_string("/apps/miro/MoviesDirectory", value)

            if not os.path.exists(value):
                os.makedirs(value)
