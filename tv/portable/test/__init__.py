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


# Includes all PyUnit unit tests

from miro.test.databasetest import *
from miro.test.templatetest import *
from miro.test.fasttypestest import *
from miro.test.schematest import *
from miro.test.storedatabasetest import *
from miro.test.olddatabaseupgradetest import *
from miro.test.databasesanitytest import *
from miro.test.subscriptiontest import *
from miro.test.schedulertest import *
from miro.test.httpclienttest import *
from miro.test.httpdownloadertest import *
from miro.test.feedtest import *
from miro.test.feedparsertest import *
from miro.test.parseurltest import *
from miro.test.utiltest import *
from miro.test.playlisttest import *
from miro.test.unicodetest import *
from miro.test.databaseupgradetest import *
from miro.test.signalstest import *
from miro.test.messagetest import *
from miro.test.strippertest import *

import miro.test.bmachinetest
