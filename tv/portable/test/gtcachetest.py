import os
import os.path
import unittest
import gettext
import logging

from miro import gtcache
from miro.test.framework import MiroTestCase
from miro.plat import resources

# FIXME this only works on GTK platforms. See #3831

# The miro.po/miro.mo file for this are in
# resources/testdata/locale/fr/LC_MESSAGES/ .
#
# If you need to add messages:
# 1. add new strings to teststring.py
# 2. run:
#
#    xgettext -k_ -kN_ -o messages.pot teststring.py
#
# 3. merge the differences between messages.pot and miro.po file
# 4. translate the new strings in miro.po
# 5. run:
#
#    msgfmt miro.po -o miro.mo

def make_french(f):
    def _make_french(*args, **kwargs):
        old_lang = None
        try:
            try:
                old_lang = os.environ["LANGUAGE"]
            except StandardError:
                pass
            os.environ["LANGUAGE"] = "fr"
            gtcache._gtcache = {}

            gettext.bindtextdomain("miro", resources.path("testdata/locale"))
            gettext.textdomain("miro")
            gettext.bind_textdomain_codeset("miro", "UTF-8")

            f(*args, **kwargs)

        finally:
            if old_lang is None:
                del os.environ["LANGUAGE"]
            else:
                os.environ["LANGUAGE"] = old_lang
    return _make_french

INPUT = "parsed %(countfiles)d files - found %(countvideos)d videos"
OUTPUT = u'%(countfiles)d fichiers analys\xe9s  - %(countvideos)d vid\xe9os trouv\xe9es'

class GettextTest(MiroTestCase):
    # FIXME - we probably want to test that something is logged instead of
    # ignoring the logging.
    def setUp(self):
        MiroTestCase.setUp(self)
        self.oldlevel = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)

    def tearDown(self):
        MiroTestCase.tearDown(self)
        logging.getLogger().setLevel(self.oldlevel)

    @make_french
    def test_gettext(self):
        self.assertEqual(gtcache.gettext("OK"), u'Valider')
        self.assertEqual(gtcache.gettext("Channels"), u'Cha\xeenes')

    @make_french
    def test_gettext_values(self):
        # test with no value expansion
        self.assertEqual(gtcache.gettext(INPUT), OUTPUT)

        # test with old value expansion
        self.assertEqual(gtcache.gettext(INPUT) % {"countfiles": 1, "countvideos": 2},
                         OUTPUT % {"countfiles": 1, "countvideos": 2})

        # test with value expansion done by gtcache.gettext
        self.assertEqual(gtcache.gettext(INPUT, 
                                         {"countfiles": 1, "countvideos": 2}),
                         OUTPUT % {"countfiles": 1, "countvideos": 2})

    @make_french
    def test_gettext_values_failures(self):
        # try gettext with a bad translation.  the string is fine, but
        # the translated version of the string is missing the d
        # characters which causes a Python formatting syntax error.
        input2 = "bad parsed %(countfiles)d files - found %(countvideos)d videos"

        # first we call gettext on the string by itself--this is fine,
        # so we should get the translated version of the string.
        self.assertEqual(gtcache.gettext(input2),
                         u'bad %(countfiles) fichiers analys\xe9s  - %(countvideos) vid\xe9os trouv\xe9es')

        # now we pass in a values dict which will kick up a ValueError
        # when trying to expand the values.  that causes gettext to
        # return the english form of the string with values expanded.
        self.assertEqual(gtcache.gettext(input2, 
                                         {"countfiles": 1, "countvideos": 2}),
                         input2 % {"countfiles": 1, "countvideos": 2})

    @make_french
    def test_ngettext(self):
        # french uses singular for 0, 1 and plural for everything else.
        self.assertEqual(gtcache.ngettext("%(count)d video found",
                                          "%(count)d videos found", 0),
                         u'%(count)d vid\xe9o trouv\xe9e')

        self.assertEqual(gtcache.ngettext("%(count)d video found",
                                          "%(count)d videos found", 1),
                         u'%(count)d vid\xe9o trouv\xe9e')

        self.assertEqual(gtcache.ngettext("%(count)d video found",
                                          "%(count)d videos found", 2),
                         u'%(count)d vid\xe9os trouv\xe9es')

    @make_french
    def test_ngettext_values(self):
        # try the bad translation with no values
        self.assertEqual(gtcache.ngettext("bad %(count)d video found",
                                          "bad %(count)d videos found", 0),
                         u'bad %(count) vid\xe9o trouv\xe9e')

        # try the bad translation with values
        self.assertEqual(gtcache.ngettext("bad %(count)d video found",
                                          "bad %(count)d videos found", 0,
                                          {"count": 0}),
                         u'bad 0 videos found')

        self.assertEqual(gtcache.ngettext("bad %(count)d video found",
                                          "bad %(count)d videos found", 1,
                                          {"count": 1}),
                         u'bad 1 video found')

        self.assertEqual(gtcache.ngettext("bad %(count)d video found",
                                          "bad %(count)d videos found", 2,
                                          {"count": 2}),
                         u'bad 2 videos found')
