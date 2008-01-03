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

"""app.py -- Stores singleton objects.

App.py is a respository for high-level singleton objects.  Most of these
objects get set in startup.py, but some get set in frontend code as well.

Here is the list of objects that app currently stores:

controller -- Handle High-level control of Miro
db -- Database object

The html frontend adds:

delegate -- UIBackendDelegate that handles platform-specific UI tasks.
htmlapp -- HTMLApplication object
"""

# NOTE: we could set controller, db, etc. to None here, but it seems better
# not do.  This way if we call "from app import controller" before the
# controller singleton is created, then we will immediately get an error.
