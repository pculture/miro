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


"""Includes all the unit tests, sets up the environment, and sets
up the testsuite.
"""

import os
import sys
from miro import app
from miro import prefs
from miro import config
from miro import httpclient
from miro.test import framework

config.load_temporary()

import unittest

from miro.test.importtest import *
from miro.test.conversionstest import *
from miro.test.devicestest import *
from miro.test.flashscrapertest import *
from miro.test.unicodetest import *
from miro.test.schematest import *
from miro.test.storedatabasetest import *
from miro.test.databasesanitytest import *
from miro.test.subscriptiontest import *
from miro.test.opmltest import *
from miro.test.schedulertest import *
from miro.test.networktest import *
from miro.test.httpclienttest import *
from miro.test.httpdownloadertest import *
from miro.test.httpauthtoolstest import *
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
from miro.test.cellpacktest import *
from miro.test.fileobjecttest import *
from miro.test.fastresumetest import *
from miro.test.widgetstateconstantstest import *
from miro.test.metadatatest import *
from miro.test.tableselectiontest import *
from miro.test.filetagstest import *
from miro.test.watchedfoldertest import *
from miro.test.subprocesstest import *
from miro.test.itemfiltertest import *
from miro.test.extensiontest import *
from miro.test.idleiteratetest import *
from miro.test.itemtracktest import *
from miro.test.itemlisttest import *
from miro.test.itemrenderertest import *
from miro.test.sharingtest import *
from miro.test.databaseerrortest import *
from miro.test.playbacktest import *

# platform specific tests

# FIXME - rework this so that platform specific tests are handled
# by decorators instead.
if app.config.get(prefs.APP_PLATFORM) == "linux":
    from miro.test.gtcachetest import *
    from miro.test.downloadertest import *
else:
    framework.skipped_tests.append("miro.test.gtcachetest tests: not linux")
    framework.skipped_tests.append("miro.test.downloadertest tests: not linux")

if app.config.get(prefs.APP_PLATFORM) == "osx":
    from miro.test.osxsparkletest import *
else:
    framework.skipped_tests.append("miro.test.sparkletest tests: not osx")

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

def stop_on_failure(runner, result, meth):
    def _wrapped_meth(*args, **kwargs):
        runner.failed_fast = True
        result.stop()
        return meth(*args, **kwargs)
    return _wrapped_meth

class MiroTestRunner(unittest.TextTestRunner):
    def __init__(self, stream=sys.stderr, descriptions=1, verbosity=1,
                 failfast=False):
        unittest.TextTestRunner.__init__(self, stream, descriptions, verbosity)
        self.failfast = failfast
        if failfast:
            self.stream.write("Tests set to stop on first failure.\n")
        self.failed_fast = False

    def _makeResult(self):
        result = unittest.TextTestRunner._makeResult(self)
        if self.failfast:
            result.addFailure = stop_on_failure(self, result, result.addFailure)
            result.addError = stop_on_failure(self, result, result.addError)
        return result

    def run(self, suite):
        self.before_run()
        try:
            return unittest.TextTestRunner.run(self, suite)
        finally:
            self.after_run()

    def before_run(self):
        # libcurl can only be initialized/cleaned up once per run, so this code
        # can't go in the setUp/tearDown methosd.
        httpclient.init_libcurl()

    def after_run(self):
        httpclient.cleanup_libcurl()
        from miro.test import framework
        framework.clean_up_temp_files()
        if self.failed_fast:
            self.stream.write(
                "Stopped on first failure!  Not all tests were run!\n")
        for mem in framework.skipped_tests:
            self.stream.write("Skipped: %s\n" % mem)

def run_tests():
    failfast = False
    verbosity = 1
    if "--failfast" in sys.argv:
        sys.argv.remove("--failfast")
        failfast = True
    while "-v" in sys.argv:
        sys.argv.remove("-v")
        verbosity += 1
    from miro import test
    unittest.main(
        module=test, testLoader=MiroTestLoader(),
        testRunner=MiroTestRunner(failfast=failfast, verbosity=verbosity))
