"""
See tv/resources/testdata/stripperdata/ for test files.

Files ending with ``.in`` are input files.  These should be in utf-8 coding
and the entire file is used as input.

Files ending with ``.expected`` are expected output files.  These files are
the repr(...) of the output from HTMLStripper.strip.

If you need to write new tests, write the test, run the unittest and the
test will fail--but StripperTest will tell you what the output is.  You can
verify the output, then copy and paste it into a .expected file.
"""

from StringIO import StringIO

import os.path
import os
from miro.test.framework import MiroTestCase
from miro import util
from miro.plat import resources

class HTMLStripperTest(MiroTestCase):
    def test_garbage(self):
        stripper = util.HTMLStripper()

        for mem in [(1, ("", [])),
                    (None, ("", [])),
                    ({}, ("", []))
                    ]:
            self.assertEquals(stripper.strip(mem[0]), mem[1])

        for mem in [("<html>", ("", [])),
                    ("<html></html>", ("", []))]:
            self.assertEquals(stripper.strip(mem[0]), mem[1])

    def test_simple(self):
        stripper = util.HTMLStripper()

        for mem in [("<html", ("<html", [])),
                    ("<html><html>", ("", [])),
                    ("</html></html>", ("", [])),
                    ("<p>foo</p>", ("foo", [])),
                    ("<p>foo</p><br/>", ("foo", []))
                    ]:
            self.assertEquals(stripper.strip(mem[0]), mem[1])

    def test_stripper_data(self):
        stripper = util.HTMLStripper()

        testdir = resources.path("testdata/stripperdata")
        tests = [m for m in os.listdir(testdir) if m.endswith(".in")]

        for mem in tests:
            mem = os.path.join(testdir, mem)
            if not os.path.isfile(mem):
                continue

            f = open(mem, "r")
            input = f.read()
            f.close()

            input = input.decode("utf-8")
            output = stripper.strip(input)

            expected = os.path.splitext(mem)[0] + ".expected"
            if not os.path.isfile(expected):
                print "%s not found." % expected
                print "Input:"
                print "%s" % repr(input)
                print "Output:"
                print "%s" % repr(output)
                self.assertEquals(0, 1)
            else:
                f = open(expected, "r")
                data = f.read().strip()
                f.close()
                try:
                    self.assertEquals(repr(output), data)
                except AssertionError:
                    print "Output:"
                    print "%s" % repr(output)
                    raise
