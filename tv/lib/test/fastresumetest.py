import errno
import sys
import os
import tempfile
import shutil

from miro import prefs
from miro import app
from miro.test.framework import MiroTestCase
from miro.dl_daemon.download import (save_fast_resume_data,
                                     load_fast_resume_data,
                                     generate_fast_resume_filename)

FAKE_INFO_HASH = 'PINKPASTA'
FAKE_RESUME_DATA = 'BEER'
  
class FastResumeTest(MiroTestCase):
    def setUp(self):
        self.sandbox_support_directory = tempfile.mkdtemp()
        self.old_support_directory = app.config.get(prefs.SUPPORT_DIRECTORY)
        app.config.set(prefs.SUPPORT_DIRECTORY, self.sandbox_support_directory)

    def tearDown(self): 
        try:
            shutil.rmtree(self.sandbox_support_directory)
        except OSError, e:
            assert 0, "test teardown failed"
        app.config.set(prefs.SUPPORT_DIRECTORY, self.old_support_directory)

    # test_resume_data: Test easy load/store.
    def test_resume_data(self):
        save_fast_resume_data(FAKE_INFO_HASH, FAKE_RESUME_DATA)
        data = load_fast_resume_data(FAKE_INFO_HASH)
        self.assertEquals(FAKE_RESUME_DATA, data)

    # Precreate the file but lock down the file so the file open fails.
    def test_save_fast_resume_data_bad(self):
        # Grab the filename that will be used
        filename = generate_fast_resume_filename(FAKE_INFO_HASH)
        # Create the file
        os.makedirs(os.path.dirname(filename))
        f = open(filename, 'wb')
        f.close()
        os.chmod(filename, 0)
        save_fast_resume_data(FAKE_INFO_HASH, FAKE_RESUME_DATA)
        # We did not lock down the directory so check save_fast_resume_data
        # nuked the file for us.
        self.assertFalse(os.path.exists(filename))

    # Try to load a unreadable file so the load fails.
    def test_load_fast_resume_data_bad(self):
        # Grab the filename that will be used
        filename = generate_fast_resume_filename(FAKE_INFO_HASH)
        # Create the file
        os.makedirs(os.path.dirname(filename))
        f = open(filename, 'wb')
        f.close()
        old_mode = os.stat(filename).st_mode
        os.chmod(filename, 0)
        data = load_fast_resume_data(FAKE_INFO_HASH)
        self.assertEquals(data, None)
        os.chmod(filename, old_mode)
