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


# Includes all PyUnit unit tests

import unittest

from test.databasetest import *
from test.templatetest import *
from test.fasttypestest import *
from test.schematest import *
from test.storedatabasetest import *
from test.olddatabaseupgradetest import *
from test.databasesanitytest import *
from test.subscriptiontest import *
from test.schedulertest import *
from test.httpclienttest import *
from test.httpdownloadertest import *
from test.feedtest import *
from test.feedparsertest import *
from test.parseurltest import *
from test.utiltest import *
from test.playlisttest import *
from test.unicodetest import *
from test.databaseupgradetest import *
import test.bmachinetest
