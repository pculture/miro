# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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


"""Includes all the unit tests, sets up the environment, and sets
up the testsuite.
"""

from miro import app
from miro import prefs
from miro import config

config.load_temporary()

import unittest

from miro.test.importtest import *
from miro.test.conversionstest import *
from miro.test.flashscrapertest import *
from miro.test.unicodetest import *
from miro.test.datastructurestest import *
from miro.test.schematest import *
from miro.test.storedatabasetest import *
from miro.test.databasesanitytest import *
from miro.test.subscriptiontest import *
from miro.test.opmltest import *
from miro.test.schedulertest import *
from miro.test.networktest import *
from miro.test.httpclienttest import *
from miro.test.httpdownloadertest import *
from miro.test.feedtest import *
from miro.test.feedparsertest import *
from miro.test.parseurltest import *
from miro.test.utiltest import *
from miro.test.playlisttest import *
from miro.test.signalstest import *
from miro.test.messagetest import *
from miro.test.strippertest import *
from miro.test.xhtmltest import *
from miro.test.iconcachetest import *
from miro.test.databasetest import *
from miro.test.itemtest import *
from miro.test.filetypestest import *

# platform specific tests
if app.config.get(prefs.APP_PLATFORM) == "linux":
    from miro.test.gtcachetest import *
    from miro.test.downloadertest import *
elif app.config.get(prefs.APP_PLATFORM) == "osx":
    from miro.test.sparkletest import *

class MiroTestLoader(unittest.TestLoader):
    def loadTestsFromNames(self, names, module):
        self._check_for_performance_tests(names, module)
        return unittest.TestLoader.loadTestsFromNames(self, names, module)

    def _check_for_performance_tests(self, names, module):
        # Only run the performance tests if they are specifically listed in
        # arguments.
        from miro import test as my_module
        if module is my_module:
            for name in names:
                if 'performancetest' in name:
                    self._add_performance_tests()
                    break

    def _add_performance_tests(self):
        from miro.test import performancetest
        for name in dir(performancetest):
            obj = getattr(performancetest, name)
            globals()[name] = obj

def run_tests():
    import sys
    from miro import httpclient
    from miro import test
    # libcurl can only be initialized/cleaned up once per run, so this code
    # can't go in the setUp/tearDown methosd.
    httpclient.init_libcurl()
    unittest.main(module=test, testLoader=MiroTestLoader())
    httpclient.cleanup_libcurl()
    from miro.test import framework
    framework.clean_up_temp_files()
