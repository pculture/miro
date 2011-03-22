# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""miro.frontends.profilewidgets -- Psuedo-frontend for profiling the UI
"""

import types

from miro.plat.frontends.widgets import application as plat_application
from miro.frontends.profilewidgets import tests
from miro.frontends.profilewidgets import portable
from miro.frontends.widgets import application

def run_application():
    app = build_platform_app()
    portable.setup()

    # monkey patch the startup method so that we don't startup the miro
    # backend.  Dirty, but it works.
    app.startup = tests.startup
    app.run()
    app.setup_globals()

def build_platform_app():
    for name in dir(plat_application):
        obj = getattr(plat_application, name)
        if (type(obj) in (types.ClassType, type)
                and issubclass(obj, application.Application)
                and obj is not application.Application):
            return obj()
    raise AssertionError("Can't find application class")
