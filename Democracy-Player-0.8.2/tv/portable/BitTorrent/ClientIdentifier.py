# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

import re

matches = (
           ('-AZ(?P<version>\d+)-+.+$'     , "Azureus"             ),
           ('M(?P<version>\d-\d-\d)--.+$'  , "BitTorrent"          ),
           ('T(?P<version>\d+)-+.+$'       , "BitTornado"          ),
           ('-TS(?P<version>\d+)-+.+$'     , "TorrentStorm"        ),
           ('S(?P<version>\d+[\dAB])-+.+$' , "Shadow's"            ),
           ('A(?P<version>\d+)-+.+$'       , "ABC"                 ),
           ('-G3.+$'                       , "G3Torrent"           ),
           ('exbc.+$'                      , "BitComet"            ),
           ('-LT(?P<version>\d+)-+.+$'     , "libtorrent"          ),
           ('Mbrst(?P<version>\d-\d-\d).+$', "burst!"              ),
           ('-BB(?P<version>\d+)-+.+$'     , "BitBuddy"            ),
           ('-CT(?P<version>\d+)-+.+$'     , "CTorrent"            ),
           ('-MT(?P<version>\d+)-+.+$'     , "MoonlightTorrent"    ),
           ('-BX(?P<version>\d+)-+.+$'     , "BitTorrent X"        ),
           ('-TN(?P<version>\d+)-+.+$'     , "TorrentDotNET"       ),
           ('-SS(?P<version>\d+)-+.+$'     , "SwarmScope"          ),
           ('-XT(?P<version>\d+)-+.+$'     , "XanTorrent"          ),
           ('U(?P<version>\d+)-+.+$'       , "UPnP NAT Bit Torrent"),
           )

matches = [(re.compile(pattern, re.DOTALL), name) for pattern, name in matches]

def identify_client(peerid):
    client = 'unknown'
    version = ''
    for pat, name in matches:
        m = pat.match(peerid)
        if m:
            client = name
            d = m.groupdict()
            if d.has_key('version'):
                version = d['version']
                version = version.replace('-','.')
                if version.find('.') == -1:
                    version = '.'.join(version)
            break
    return client, version
