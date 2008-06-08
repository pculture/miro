# Miro - an RSS based video player application
# Copyright (C) 2008 Participatory Culture Foundation
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

from os import getenv
import os.path

# for technical specifications on u3 stuff, see 
# http://www.u3.com/developers/default.aspx

# strings to mark places where we need to expand to actual paths
APP_DATA_PREFIX = u"$APP_DATA_PATH"
DEVICE_DOCUMENT_PREFIX = u"$DEVICE_DOCUMENT_PATH"

# directory on the u3 drive for application data
# stored here: preferences, db
app_data_path = getenv("U3_APP_DATA_PATH")
if app_data_path:
    app_data_path = os.path.normcase(app_data_path)

# directory on the u3 drive for user data
# stored here: downloads
device_document_path = getenv("U3_DEVICE_DOCUMENT_PATH")
if device_document_path:
    device_document_path = os.path.normcase(device_document_path)

# whether we're in u3 mode or not
u3_active = app_data_path is not None and device_document_path is not None and os.path.isdir(app_data_path) and os.path.isdir(device_document_path)

