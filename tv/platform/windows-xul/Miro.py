# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""Startup the Main Miro process."""


def startup():
    theme = None
    # Should have code to figure out the theme.

    from miro.plat import pipeipc
    try:
        pipe_server = pipeipc.Server()
    except pipeipc.PipeExists:
        pipeipc.send_command_line_args()
        return
    pipe_server.start_process()

    from miro.plat.utils import initializeLocale
    initializeLocale()

    from miro import gtcache
    gtcache.init()

    from miro import startup
    startup.initialize(theme)

    from miro.plat import migrateappname
    migrateappname.migrateSupport('Democracy', 'Miro')

    from miro import singleclick
    from miro.plat import commandline
    singleclick.set_command_line_args(commandline.get_command_line()[1:])

    # Kick off the application
    from miro.plat.frontends.widgets.application import WindowsApplication
    WindowsApplication().run()
    pipe_server.quit()

startup()
