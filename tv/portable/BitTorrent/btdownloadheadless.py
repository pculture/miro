#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTorrent.download import download
from threading import Event
from os.path import abspath
from sys import argv, stdout
from cStringIO import StringIO
from time import time

def hours(n):
    if n == -1:
        return '<unknown>'
    if n == 0:
        return 'complete!'
    n = long(n)
    h, r = divmod(n, 60 * 60)
    m, sec = divmod(r, 60)
    if h > 1000000:
        return '<unknown>'
    if h > 0:
        return '%d hour %02d min %02d sec' % (h, m, sec)
    else:
        return '%d min %02d sec' % (m, sec)

class HeadlessDisplayer:
    def __init__(self):
        self.done = False
        self.file = ''
        self.percentDone = ''
        self.timeEst = ''
        self.downloadTo = ''
        self.downRate = ''
        self.upRate = ''
        self.downTotal = ''
        self.upTotal = ''
        self.errors = []
        self.last_update_time = 0

    def finished(self):
        self.done = True
        self.percentDone = '100'
        self.timeEst = 'Download Succeeded!'
        self.downRate = ''
        self.display({})

    def failed(self):
        self.done = True
        self.percentDone = '0'
        self.timeEst = 'Download Failed!'
        self.downRate = ''
        self.display({})

    def error(self, errormsg):
        self.errors.append(errormsg)
        self.display({})

    def display(self, dict):
        if self.last_update_time + 0.1 > time() and dict.get('fractionDone') not in (0.0, 1.0) and not dict.has_key('activity'):
            return
        self.last_update_time = time()
        if dict.has_key('spew'):
            print_spew(dict['spew'])
        if dict.has_key('fractionDone'):
            self.percentDone = str(float(int(dict['fractionDone'] * 1000)) / 10)
        if dict.has_key('timeEst'):
            self.timeEst = hours(dict['timeEst'])
        if dict.has_key('activity') and not self.done:
            self.timeEst = dict['activity']
        if dict.has_key('downRate'):
            self.downRate = '%.2f kB/s' % (float(dict['downRate']) / (1 << 10))
        if dict.has_key('upRate'):
            self.upRate = '%.2f kB/s' % (float(dict['upRate']) / (1 << 10))
        if dict.has_key('upTotal'):
            self.upTotal = '%.1f MiB' % (dict['upTotal'])
        if dict.has_key('downTotal'):
            self.downTotal = '%.1f MiB' % (dict['downTotal'])
        print '\n\n'
        for err in self.errors:
            print 'ERROR:\n' + err + '\n'
        print 'saving:        ', self.file
        print 'percent done:  ', self.percentDone
        print 'time left:     ', self.timeEst
        print 'download to:   ', self.downloadTo
        if self.downRate != '':
            print 'download rate: ', self.downRate
        if self.upRate != '':
            print 'upload rate:   ', self.upRate
        if self.downTotal != '':
            print 'download total:', self.downTotal
        if self.upTotal != '':
            print 'upload total:  ', self.upTotal
        stdout.flush()

    def chooseFile(self, default, size, saveas, dir):
        self.file = '%s (%.1f MB)' % (default, float(size) / (1 << 20))
        if saveas != '':
            default = saveas
        self.downloadTo = abspath(default)
        return default

    def newpath(self, path):
        self.downloadTo = path

def print_spew(spew):
    s = StringIO()
    s.write('\n\n\n')
    for c in spew:
        s.write('%20s ' % c['ip'])
        if c['initiation'] == 'local':
            s.write('l')
        else:
            s.write('r')
        rate, interested, choked = c['upload']
        s.write(' %10s ' % str(int(rate)))
        if c['is_optimistic_unchoke']:
            s.write('*')
        else:
            s.write(' ')
        if interested:
            s.write('i')
        else:
            s.write(' ')
        if choked:
            s.write('c')
        else:
            s.write(' ')

        rate, interested, choked, snubbed = c['download']
        s.write(' %10s ' % str(int(rate)))
        if interested:
            s.write('i')
        else:
            s.write(' ')
        if choked:
            s.write('c')
        else:
            s.write(' ')
        if snubbed:
            s.write('s')
        else:
            s.write(' ')
        s.write('\n')
    print s.getvalue()

def run(params):
    try:
        import curses
        curses.initscr()
        cols = curses.COLS
        curses.endwin()
    except:
        cols = 80

    h = HeadlessDisplayer()
    download(params, h.chooseFile, h.display, h.finished, h.error, Event(), cols, h.newpath)
    if not h.done:
        h.failed()

if __name__ == '__main__':
    run(argv[1:])
