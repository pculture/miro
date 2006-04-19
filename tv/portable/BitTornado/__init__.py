product_name = 'BitTornado'

version = "T-0.3.7 (BitTornado)"

version_short = version.split(' ')[0]

report_email = version_short+"@degreez.net"

from types import StringType
from sha import sha
from time import time, clock
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

__root__ = [None]

def resetPeerIDs():
    try:
        f = open('/dev/urandom','rb')
        x = f.read(20)
        f.close()
    except:
        x = ''

    l1 = 0
    t = clock()
    while t == clock():
        l1 += 1
    l2 = 0
    t = long(time()*100)
    while t == long(time()*100):
        l2 += 1
    l3 = 0
    if l2 < 1000:
        t = long(time()*10)
        while t == long(clock()*10):
            l3 += 1
    x += ( repr(time()) + '/' + str(time()) + '/'
           + str(l1) + '/' + str(l2) + '/' + str(l3) + '/'
           + str(getpid()) )
        
    root = ''
    for i in sha(x).digest()[-11:]:
        root += mapbase64[ord(i) & 0x3F]
    __root__[0] = root
        
resetPeerIDs()

def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    myid = version_short[0]
    for subver in version_short[2:].split('.'):
        try:
            subver = int(subver)
        except:
            subver = 0
        myid += mapbase64[subver]
    myid += ('-' * (6-len(myid)))
    myid += ins + __root__[0]

    return myid