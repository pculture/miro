#!/usr/bin/env python

# Written by Henry 'Pi' James
# see LICENSE.txt for license information

from BitTorrent.download import download
from threading import Event
from os.path import abspath
from signal import signal, SIGWINCH
from sys import argv, stdout
from time import strftime, time

def fmttime(n):
    if n == -1:
        return 'download not progressing (file not being uploaded by others?)'
    if n == 0:
        return 'download complete!'
    n = int(n)
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    if h > 1000000:
        return 'n/a'
    return 'finishing in %d:%02d:%02d' % (h, m, s)

def commaize(n): 
    s = str(n)
    commad = s[-3:]
    while len(s) > 3:
        s = s[:-3]
        commad = '%s,%s' % (s[-3:], commad)
    return commad

def fmtsize(n, baseunit = 0, padded = 1):
    unit = [' B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = baseunit
    while i + 1 < len(unit) and n >= 999:
        i += 1
        n = float(n) / (1 << 10)
    size = ''
    if padded:
        if n < 10:
            size = '  '
        elif n < 100:
            size = ' '
    if i != 0:
        size += '%.1f %s' % (n, unit[i])
    else:
        if padded:
            size += '%.0f   %s' % (n, unit[i])
        else: 
            size += '%.0f %s' % (n, unit[i])
    return size

def winch_handler(signum, stackframe):
    global scrwin, scrpan, labelwin, labelpan, fieldw, fieldh, fieldwin, fieldpan
    # SIGWINCH. Remake the frames!
    ## Curses Trickery
    curses.endwin()
    # delete scrwin somehow?
    scrwin.refresh()
    scrwin = curses.newwin(0, 0, 0, 0) 
    scrh, scrw = scrwin.getmaxyx()
    scrpan = curses.panel.new_panel(scrwin)
    labelh, labelw, labely, labelx = scrh - 2, 9, 1, 2
    labelwin = curses.newwin(labelh, labelw, labely, labelx)
    labelpan = curses.panel.new_panel(labelwin)
    fieldh, fieldw, fieldy, fieldx = scrh - 2, scrw - 2 - labelw - 3, 1, labelw + 3
    fieldwin = curses.newwin(fieldh, fieldw, fieldy, fieldx)
    fieldpan = curses.panel.new_panel(fieldwin)
    prepare_display()

# This flag stops the torrent when set.
mainkillflag = Event()

class CursesDisplayer:
    def __init__(self, mainerrlist):
        self.done = 0
        self.file = ''
        self.fileSize = ''
        self.activity = ''
        self.status = ''
        self.progress = ''
        self.downloadTo = ''
        self.downRate = '%s/s down' % (fmtsize(0))
        self.upRate = '%s/s up  ' % (fmtsize(0))
        self.upTotal = '%s   up  ' % (fmtsize(0, 2))
        self.downTotal = '%s   down' % (fmtsize(0, 2))
        self.errors = []
        self.globalerrlist = mainerrlist
        self.last_update_time = 0

    def finished(self):
        self.done = 1
        self.activity = 'download succeeded!'
        self.downRate = '%s/s down' % (fmtsize(0))
        self.display({'fractionDone': 1})

    def failed(self):
        global mainkillflag
        if not mainkillflag.isSet():
            self.done = 1
            self.activity = 'download failed!'
            self.downRate = '%s/s down' % (fmtsize(0))
            self.display()

    def error(self, errormsg):
        errtxt = strftime('[%H:%M:%S] ') + errormsg
        self.errors.append(errtxt)
        self.globalerrlist.append(errtxt)
        # force redraw to get rid of nasty stack backtrace
        winch_handler(SIGWINCH, 0)
        self.display()

    def display(self, dict = {}):
        if self.last_update_time + 0.1 > time() and dict.get('fractionDone') not in (0.0, 1.0) and not dict.has_key('activity'):
            return
        self.last_update_time = time()
        global mainkillflag
        fractionDone = dict.get('fractionDone', None)
        timeEst = dict.get('timeEst', None)
        downRate = dict.get('downRate', None)
        upRate = dict.get('upRate', None)
        downTotal = dict.get('downTotal', None) # total download megs, float
        upTotal = dict.get('upTotal', None) # total upload megs, float
        activity = dict.get('activity', None)
        if activity is not None and not self.done:
            self.activity = activity
        elif timeEst is not None:
            self.activity = fmttime(timeEst)
        if fractionDone is not None:
            blocknum = int(fieldw * fractionDone)
            self.progress = blocknum * '#' + (fieldw - blocknum) * '_'
            self.status = '%s (%.1f%%)' % (self.activity, fractionDone * 100)
        else:
            self.status = self.activity
        if downRate is not None:
            self.downRate = '%s/s down' % (fmtsize(float(downRate)))
        if upRate is not None:
            self.upRate = '%s/s up  ' % (fmtsize(float(upRate)))
        if upTotal is not None:
            self.upTotal = '%s   up  ' % (fmtsize(upTotal, 2))
        if downTotal is not None:
            self.downTotal = '%s   down' % (fmtsize(downTotal, 2))
        inchar = fieldwin.getch()
        if inchar == 12: #^L
            winch_handler(SIGWINCH, 0)
        elif inchar == ord('q'):  # quit 
            mainkillflag.set() 
            self.status = 'shutting down...'
        try:
            fieldwin.erase()
            fieldwin.addnstr(0, 0, self.file, fieldw, curses.A_BOLD)
            fieldwin.addnstr(1, 0, self.fileSize, fieldw)
            fieldwin.addnstr(2, 0, self.downloadTo, fieldw)
            if self.progress:
                fieldwin.addnstr(3, 0, self.progress, fieldw, curses.A_BOLD)
            fieldwin.addnstr(4, 0, self.status, fieldw)
            fieldwin.addnstr(5, 0, self.downRate + ' - ' + self.upRate, fieldw / 2)
            fieldwin.addnstr(6, 0, self.downTotal + ' - ' + self.upTotal, fieldw / 2)

            if self.errors:
                errsize = len(self.errors)
                for i in range(errsize):
                    if (7 + i) >= fieldh:
                        break
                    fieldwin.addnstr(7 + i, 0, self.errors[errsize - i - 1], fieldw, curses.A_BOLD)
            else:
                fieldwin.move(7, 0)
        except curses.error: 
            pass

        curses.panel.update_panels()
        curses.doupdate()

    def chooseFile(self, default, size, saveas, dir):
        self.file = default
        self.fileSize = '%s (%s)' % (commaize(size), fmtsize(size, padded = 0))
        if saveas == '':
            saveas = default
        self.downloadTo = abspath(saveas)
        return saveas

def run(mainerrlist, params):
    d = CursesDisplayer(mainerrlist)
    try:
        download(params, d.chooseFile, d.display, d.finished, d.error, mainkillflag, fieldw)
    except KeyboardInterrupt:
        # ^C to exit.. 
        pass 
    if not d.done:
        d.failed()

def prepare_display():
    try:
        scrwin.border(ord('|'),ord('|'),ord('-'),ord('-'),ord(' '),ord(' '),ord(' '),ord(' '))
        labelwin.addstr(0, 0, 'file:')
        labelwin.addstr(1, 0, 'size:')
        labelwin.addstr(2, 0, 'dest:')
        labelwin.addstr(3, 0, 'progress:')
        labelwin.addstr(4, 0, 'status:')
        labelwin.addstr(5, 0, 'speed:')
        labelwin.addstr(6, 0, 'totals:')
        labelwin.addstr(7, 0, 'error(s):')
    except curses.error: 
        pass
    fieldwin.nodelay(1)
    curses.panel.update_panels()
    curses.doupdate()

try:
    import curses
    import curses.panel

    scrwin = curses.initscr()
    curses.noecho()
    curses.cbreak()

except:
    print 'Textmode GUI initialization failed, cannot proceed.'
    print
    print 'This download interface requires the standard Python module ' \
       '"curses", which is unfortunately not available for the native ' \
       'Windows port of Python. It is however available for the Cygwin ' \
       'port of Python, running on all Win32 systems (www.cygwin.com).'
    print
    print 'You may still use "btdownloadheadless.py" to download.'

scrh, scrw = scrwin.getmaxyx()
scrpan = curses.panel.new_panel(scrwin)
labelh, labelw, labely, labelx = scrh - 2, 9, 1, 2
labelwin = curses.newwin(labelh, labelw, labely, labelx)
labelpan = curses.panel.new_panel(labelwin)
fieldh, fieldw, fieldy, fieldx = scrh - 2, scrw - 2 - labelw - 3, 1, labelw + 3
fieldwin = curses.newwin(fieldh, fieldw, fieldy, fieldx)
fieldpan = curses.panel.new_panel(fieldwin)
prepare_display()

signal(SIGWINCH, winch_handler)

if __name__ == '__main__':
    mainerrlist = []
    try:
        run(mainerrlist, argv[1:])
    finally:
        curses.nocbreak()
        curses.echo()
        curses.endwin()
    if len(mainerrlist) != 0:
       print "These errors occurred during execution:"
       for error in mainerrlist:
          print error

