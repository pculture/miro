#!/usr/bin/python

import urllib

def download_release(releaseid, filename=None):
    if filename is None:
        filename = str(releaseid)
    print 'generating %s from %s' % (filename, releaseid)
    url =('http://api.7digital.com/1.2/release/details'
          '?releaseid=%s'
          '&imageSize=350'
          '&oauth_consumer_key=7d35gcbnycah' % releaseid)
    reply = urllib.urlopen(url).read()
    open(filename, 'wb').write(reply)

# bossanova
download_release(189844)
# all billie jean releases
for releaseid in [ 518377, 280410, 307167, 289401, 282494, 282073, 624250,
                  312343, 391641, 341656, 284075, 280538, 283379, 312343,
                  669160, 391639, ]:
    download_release(releaseid)
# releaseid that doesn't match
download_release(1, 'no-matches')
