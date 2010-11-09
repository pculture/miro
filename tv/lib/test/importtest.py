import os
import tempfile
import urllib
from miro.test.framework import MiroTestCase
from StringIO import StringIO

from miro.importmedia import import_itunes_path

# Provide a file template which we can use to replace with different paths
# to test.  This is taken from a fresh installation of iTunes 10 on the Mac
# using English locale.  I manually changed a ' double byte representation to
# a ascii one to prevent Python whinging.
#
# Silly linebreaks but I don't want to format it any more than necessary to
# stash it here.
file_template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Major Version</key><integer>1</integer>
	<key>Minor Version</key><integer>1</integer>
	<key>Application Version</key><string>10.0.1</string>
	<key>Features</key><integer>5</integer>
	<key>Show Content Ratings</key><true/>
	<key>Music Folder</key><string>%(path)s</string>
	<key>Library Persistent ID</key><string>A71BE5E01C63D585</string>
	<key>Tracks</key>
	<dict>
	</dict>
	<key>Playlists</key>
	<array>
		<dict>
			<key>Name</key><string>Library</string>
			<key>Master</key><true/>
			<key>Playlist ID</key><integer>66</integer>
			<key>Playlist Persistent ID</key><string>2F413BBF60F29044</string>
			<key>Visible</key><false/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>Music</string>
			<key>Playlist ID</key><integer>122</integer>
			<key>Playlist Persistent ID</key><string>19869D852C060ACB</string>
			<key>Distinguished Kind</key><integer>4</integer>
			<key>Music</key><true/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>Movies</string>
			<key>Playlist ID</key><integer>125</integer>
			<key>Playlist Persistent ID</key><string>35FFC6B69B9588D9</string>
			<key>Distinguished Kind</key><integer>2</integer>
			<key>Movies</key><true/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>TV Shows</string>
			<key>Playlist ID</key><integer>128</integer>
			<key>Playlist Persistent ID</key><string>80FD702CB081E1BA</string>
			<key>Distinguished Kind</key><integer>3</integer>
			<key>TV Shows</key><true/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>Podcasts</string>
			<key>Playlist ID</key><integer>116</integer>
			<key>Playlist Persistent ID</key><string>771FE9B31BD381BE</string>
			<key>Distinguished Kind</key><integer>10</integer>
			<key>Podcasts</key><true/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>iTunes DJ</string>
			<key>Playlist ID</key><integer>109</integer>
			<key>Playlist Persistent ID</key><string>275D96DAC10E2D55</string>
			<key>Distinguished Kind</key><integer>22</integer>
			<key>Party Shuffle</key><true/>
			<key>All Items</key><true/>
		</dict>
		<dict>
			<key>Name</key><string>90's Music</string>
			<key>Playlist ID</key><integer>69</integer>
			<key>Playlist Persistent ID</key><string>4F1C142FCB427877</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcAAAEAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABEAAAAAAAAB8YAAAAAAAAAAAAAAAAAAAAB
			AAAAAAAAB88AAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQEA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABgFNMc3QAAQAB
			AAAAAgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8AAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAARAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAB
			AAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPAAABAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEQAAAAAAAAAIAAAAAAAAAAA
			AAAAAAAAAAEAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAA==
			</data>
		</dict>
		<dict>
			<key>Name</key><string>Classical Music</string>
			<key>Playlist ID</key><integer>87</integer>
			<key>Playlist Persistent ID</key><string>D576CD873CD1CE72</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAQAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGAU0xzdAABAAEAAAACAAAAAQAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAADwAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAABEAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAB
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8AAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAARAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAg
			AAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAnpTTHN0AAEAAQAAAAcAAAAB
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAACAEAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAABIAQwBsAGEAcwBzAGkAYwBhAGwAAAAIAQAAAQAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEABLAGwAYQBzAHMAaQBlAGsAAAAI
			AQAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEgBD
			AGwAYQBzAHMAaQBxAHUAZQAAAAgBAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAOAEsAbABhAHMAcwBpAGsAAAAIAQAAAQAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEABDAGwAYQBzAHMAaQBjAGEAAAAI
			AQAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACjCv
			MOkwtzDDMK8AAAAIAQAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAADgBDAGwA4QBzAGkAYwBh
			</data>
		</dict>
		<dict>
			<key>Name</key><string>Music Videos</string>
			<key>Playlist ID</key><integer>84</integer>
			<key>Playlist Persistent ID</key><string>56FB50D92FC0A5B3</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADwAAAQAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABEAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAB
			AAAAAAAAACAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAA=
			</data>
		</dict>
		<dict>
			<key>Name</key><string>My Top Rated</string>
			<key>Playlist ID</key><integer>72</integer>
			<key>Playlist Persistent ID</key><string>9F1A7822A358D0EF</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABkAAAAQAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABEAAAAAAAAADwAAAAAAAAAAAAAAAAAAAAB
			AAAAAAAAADwAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAA=
			</data>
		</dict>
		<dict>
			<key>Name</key><string>Recently Added</string>
			<key>Playlist ID</key><integer>81</integer>
			<key>Playlist Persistent ID</key><string>F8C3EB24D965C9A9</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAIAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABELa4tri2uLa7//////////gAAAAAACTqA
			La4tri2uLa4AAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA5AgAAAQAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARAAAAAAAAAAB
			AAAAAAAAAAAAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAA
			AAAAAAAA
			</data>
		</dict>
		<dict>
			<key>Name</key><string>Recently Played</string>
			<key>Playlist ID</key><integer>78</integer>
			<key>Playlist Persistent ID</key><string>893422EE4CC27175</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABcAAAIAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABELa4tri2uLa7//////////gAAAAAACTqA
			La4tri2uLa4AAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA5AgAAAQAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARAAAAAAAAAAB
			AAAAAAAAAAAAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAA
			AAAAAAAA
			</data>
		</dict>
		<dict>
			<key>Name</key><string>Top 25 Most Played</string>
			<key>Playlist ID</key><integer>75</integer>
			<key>Playlist Persistent ID</key><string>F64DEA0DF3E2666D</string>
			<key>All Items</key><true/>
			<key>Smart Info</key>
			<data>
			AQEBAwAAABkAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAA==
			</data>
			<key>Smart Criteria</key>
			<data>
			U0xzdAABAAEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADkCAAABAAAAAAAAAAAAAAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAB
			AAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWAAAAEAAA
			AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARAAAAAAAAAAA
			AAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAA
			AAAAAAAA
			</data>
		</dict>
	</array>
</dict>
</plist>
"""

class Test_import_itunes(MiroTestCase):
    def setUp(self):
        ITUNES_FILE = "iTunes Music Library.xml"

        # import_itunes_path expects a named file directory path that
        # contains filename ITUNES_FILE underneath it.
        fd = -1
        self.tmpf_path = os.path.join(tempfile.gettempdir(), ITUNES_FILE)
        fd = os.open(self.tmpf_path, os.O_RDWR | os.O_CREAT | os.O_EXCL)
        tmpf = os.fdopen(fd, 'w')
        self.tmpf = tmpf
        self.file_url = "file://localhost"

    def tearDown(self):
        os.unlink(self.tmpf_path)

    def _clean_tmpf(self):
        self.tmpf.truncate(0)
        self.tmpf.seek(0)

    def test_nofile(self):
        path = import_itunes_path("/non/existtent/path")
        self.assertEquals(path, None)

    def test_badfile(self):
        pass
        self._clean_tmpf()
        path1 = "/Users/xxx/Music/iTunes/iTunes Music/"
        file_snippet1 = file_template % dict(path=(self.file_url + path1))

        # write some junk to the file and see what happens.
        self.tmpf.write('JUNKJUNKJUNKJUNKJUNK')
        self.tmpf.flush()

        tmpf_dir = os.path.dirname(self.tmpf_path)
        path = import_itunes_path(tmpf_dir)
        self.assertEquals(path, None)

    def test_goodfile(self):
        # Our file templates.  Try a vanilla version and one with escapes.
        # NB:
        # This is only supported on the Mac at the moment, when 
        # windows support arrives we will need to extract the paths and
        # see what it looks like and add a test here.
        path1 = "/Users/xxx/Music/iTunes/iTunes%20Music/"
        path2 = ("/Volumes/%E3%83%9B%E3%83%BC%E3%83%A0/" +
                 "xxx/Music/iTunes/iTunes%20Media/")
        file_snippet1 = file_template % dict(path=(self.file_url + path1))
        file_snippet2 = file_template % dict(path=(self.file_url + path2))

        tmpf_dir = os.path.dirname(self.tmpf_path)
        # Test vanilla path
        self._clean_tmpf()
        self.tmpf.write(file_snippet1)
        self.tmpf.flush()
        path = import_itunes_path(tmpf_dir)
        self.assertEquals(path, urllib.url2pathname(path1))

        # Test path with utf-8 escapes
        self._clean_tmpf()
        self.tmpf.write(file_snippet2)
        self.tmpf.flush()
        path = import_itunes_path(tmpf_dir)
        self.assertEquals(path, urllib.url2pathname(path2))

