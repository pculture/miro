#!/usr/bin/env python

# Written by Michael Janssen (jamuraa at base0 dot net)
# originally heavily borrowed code from btlaunchmany.py by Bram Cohen
# and btdownloadcurses.py written by Henry 'Pi' James
# now not so much.
# fmttime and fmtsize stolen from btdownloadcurses. 
# see LICENSE.txt for license information

from BitTorrent.download import download
from threading import Thread, Event, Lock
from os import listdir
from os.path import abspath, join, exists, getsize
from sys import argv, stdout, exit
from time import sleep
from signal import signal, SIGWINCH 
import traceback

def fmttime(n):
    if n == -1:
        return 'download not progressing (no seeds?)'
    if n == 0:
        return 'download complete!'
    n = int(n)
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    if h > 1000000:
        return 'n/a'
    return 'finishing in %d:%02d:%02d' % (h, m, s)

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

def dummy(*args, **kwargs):
    pass

threads = {}
ext = '.torrent'
status = 'btlaunchmany starting..'
filecheck = Lock()
mainquitflag = Event()

def cleanup_and_quit():
    status = 'Killing torrents..'
    for file, threadinfo in threads.items(): 
        status = 'Killing torrent %s' % file
        threadinfo['kill'].set() 
        threadinfo['thread'].join() 
        del threads[file]
    displaykiller.set()
    displaythread.join()
   
def dropdir_mainloop(d, params):
    deadfiles = []
    global threads, status, mainquitflag
    while 1:
        files = listdir(d)
        # new files
        for file in files: 
            if file[-len(ext):] == ext:
                if file not in threads.keys() + deadfiles:
                    threads[file] = {'kill': Event(), 'try': 1}
                    status = 'New torrent: %s' % file
                    threads[file]['thread'] = Thread(target = StatusUpdater(join(d, file), params, file).download, name = file)
                    threads[file]['thread'].start()
        # files with multiple tries
        for file, threadinfo in threads.items():
            if threadinfo.get('timeout') == 0:
                # Zero seconds left, try and start the thing again.
                threadinfo['try'] = threadinfo['try'] + 1
                threadinfo['thread'] = Thread(target = StatusUpdater(join(d, file), params, file).download, name = file)
                threadinfo['thread'].start()
                threadinfo['timeout'] = -1
            elif threadinfo.get('timeout') > 0: 
                # Decrement our counter by 1
                threadinfo['timeout'] = threadinfo['timeout'] - 1
            elif not threadinfo['thread'].isAlive():
                # died without permission
                # if it was checking the file, it's not anymore
                if threadinfo.get('checking', None):
                    filecheck.release()
                if threadinfo.get('try') == 6: 
                    # Died on the sixth try? You're dead.
                    deadfiles.append(file)
                    status = '%s died 6 times, added to dead list' % file
                    del threads[file]
                else:
                    del threadinfo['thread']
                    threadinfo['timeout'] = 10
            # dealing with files that dissapear
            if file not in files:
                status = 'Gone torrent: %s' % file
                if threadinfo.get('timeout', -1) == -1:
                    threadinfo['kill'].set()
                    threadinfo['thread'].join()
                # if it had the lock, unlock it
                if threadinfo.get('checking', None):
                    filecheck.release()
                del threads[file]
        for file in deadfiles:
            # if the file dissapears, remove it from our dead list
            if file not in files: 
                deadfiles.remove(file)
        if mainquitflag.isSet(): 
            cleanup_and_quit()
            break
        sleep(1)

def display_thread(displaykiller, mainquitflag):
    interval = 0.1
    global threads, status
    while 1:
        inchar = mainwin.getch();
        if inchar == 12: # ^L
            winch_handler()
        elif inchar == ord('q'): # quit
            mainquitflag.set() 
        # display file info
        if (displaykiller.isSet()): 
            break
        mainwin.erase()
        winpos = 0
        totalup = 0
        totaldown = 0
        totaluptotal = 0.0
        totaldowntotal = 0.0
        for file, threadinfo in threads.items(): 
            uprate = threadinfo.get('uprate', 0)
            downrate = threadinfo.get('downrate', 0)
            uptxt = '%s/s' % fmtsize(uprate)
            downtxt = '%s/s' % fmtsize(downrate)
            uptotal = threadinfo.get('uptotal', 0.0)
            downtotal = threadinfo.get('downtotal', 0.0)
            uptotaltxt = fmtsize(uptotal, baseunit = 2)
            downtotaltxt = fmtsize(downtotal, baseunit = 2)
            filesize = threadinfo.get('filesize', 'N/A')
            mainwin.addnstr(winpos, 0, threadinfo.get('savefile', file), mainwinw - 28, curses.A_BOLD)
            mainwin.addnstr(winpos, mainwinw - 30, filesize, 8)
            mainwin.addnstr(winpos, mainwinw - 21, downtxt, 10)
            mainwin.addnstr(winpos, mainwinw - 10, uptxt, 10)
            winpos = winpos + 1
            mainwin.addnstr(winpos, 0, '^--- ', 5) 
            if threadinfo.get('timeout', 0) > 0:
                mainwin.addnstr(winpos, 6, 'Try %d: died, retrying in %d' % (threadinfo.get('try', 1), threadinfo.get('timeout')), mainwinw - 21)
            else:
                mainwin.addnstr(winpos, 6, threadinfo.get('status',''), mainwinw - 21)
            mainwin.addnstr(winpos, mainwinw - 21, downtotaltxt, 8)
            mainwin.addnstr(winpos, mainwinw - 10, uptotaltxt, 8)
            winpos = winpos + 1
            totalup += uprate
            totaldown += downrate
            totaluptotal += uptotal
            totaldowntotal += downtotal
        # display statusline
        statuswin.erase() 
        statuswin.addnstr(0, 0, status, mainwinw)
        # display totals line
        totaluptxt = '%s/s' % fmtsize(totalup)
        totaldowntxt = '%s/s' % fmtsize(totaldown)
        totaluptotaltxt = fmtsize(totaluptotal, baseunit = 2)
        totaldowntotaltxt = fmtsize(totaldowntotal, baseunit = 2)
        
        totalwin.erase()
        totalwin.addnstr(0, mainwinw - 29, 'Totals:', 7);
        totalwin.addnstr(0, mainwinw - 21, totaldowntxt, 10)
        totalwin.addnstr(0, mainwinw - 10, totaluptxt, 10)
        totalwin.addnstr(1, mainwinw - 21, totaldowntotaltxt, 8)
        totalwin.addnstr(1, mainwinw - 10, totaluptotaltxt, 8)
        curses.panel.update_panels()
        curses.doupdate()
        sleep(interval)

class StatusUpdater:
    def __init__(self, file, params, name):
        self.file = file
        self.params = params
        self.name = name
        self.myinfo = threads[name]
        self.done = 0
        self.checking = 0
        self.activity = 'starting up...'
        self.display()
        self.myinfo['errors'] = []

    def download(self): 
        download(self.params + ['--responsefile', self.file], self.choose, self.display, self.finished, self.err, self.myinfo['kill'], 80)
        status = 'Torrent %s stopped' % self.file

    def finished(self): 
        self.done = 1
        self.myinfo['done'] = 1
        self.activity = 'download succeeded!'
        self.display({'fractionDone' : 1, 'downRate' : 0})

    def err(self, msg): 
        self.myinfo['errors'].append(msg)
        # errors often come with evil tracebacks that mess up our screen.
        winch_handler()
        self.display()

    def failed(self): 
        self.activity = 'download failed!' 
        self.display() 

    def choose(self, default, size, saveas, dir):
        global filecheck
        self.myinfo['downfile'] = default
        self.myinfo['filesize'] = fmtsize(size)
        if saveas == '': 
            saveas = default
        # it asks me where I want to save it before checking the file.. 
        if exists(saveas) and (getsize(saveas) > 0):
            # file will get checked
            while (not filecheck.acquire(0) and not self.myinfo['kill'].isSet()):
                self.myinfo['status'] = 'Waiting for disk check...'
                sleep(0.1)
            if not self.myinfo['kill'].isSet():
                self.checking = 1
                self.myinfo['checking'] = 1
        self.myinfo['savefile'] = saveas
        return saveas
    
    def display(self, dict = {}):
        fractionDone = dict.get('fractionDone', None)
        timeEst = dict.get('timeEst', None)
        activity = dict.get('activity', None) 
        global filecheck, status
        if activity is not None and not self.done: 
            self.activity = activity
        elif timeEst is not None: 
            self.activity = fmttime(timeEst)
        if fractionDone is not None: 
            self.myinfo['status'] = '%s (%.1f%%)' % (self.activity, fractionDone * 100)
        else: 
            self.myinfo['status'] = self.activity
        if self.activity != 'checking existing file' and self.checking:
            # we finished checking our files. 
            filecheck.release()
            self.checking = 0
            self.myinfo['checking'] = 0
        if dict.has_key('upRate'):
            self.myinfo['uprate'] = dict['upRate']
        if dict.has_key('downRate'):
            self.myinfo['downrate'] = dict['downRate']
        if dict.has_key('upTotal'):
            self.myinfo['uptotal'] = dict['upTotal']
        if dict.has_key('downTotal'):
            self.myinfo['downtotal'] = dict['downTotal']

def prepare_display(): 
    global mainwinw, scrwin, headerwin, totalwin
    try:
        scrwin.border(ord('|'),ord('|'),ord('-'),ord('-'),ord(' '),ord(' '),ord(' '),ord(' '))
        headerwin.addnstr(0, 0, 'Filename', mainwinw - 25, curses.A_BOLD)
        headerwin.addnstr(0, mainwinw - 26, 'Size', 4);
        headerwin.addnstr(0, mainwinw - 19, 'Download', 8);
        headerwin.addnstr(0, mainwinw -  6, 'Upload', 6);
        totalwin.addnstr(0, mainwinw - 27, 'Totals:', 7);
    except curses.error:
        pass
    mainwin.nodelay(1)
    curses.panel.update_panels()
    curses.doupdate()



def winch_handler(signum = SIGWINCH, stackframe = None): 
    global scrwin, mainwin, mainwinw, headerwin, totalwin, statuswin
    global scrpan, mainpan, headerpan, totalpan, statuspan
    # SIGWINCH. Remake the frames!
    ## Curses Trickery
    curses.endwin()
    # delete scrwin somehow?
    scrwin.refresh()
    scrwin = curses.newwin(0, 0, 0, 0)
    scrh, scrw = scrwin.getmaxyx()
    scrpan = curses.panel.new_panel(scrwin)
    ### Curses Setup
    scrh, scrw = scrwin.getmaxyx()
    scrpan = curses.panel.new_panel(scrwin)
    mainwinh = scrh - 5  # - 2 (bars) - 1 (debugwin) - 1 (borderwin) - 1 (totalwin)
    mainwinw = scrw - 4  # - 2 (bars) - 2 (spaces)
    mainwiny = 2         # + 1 (bar) + 1 (titles)
    mainwinx = 2         # + 1 (bar) + 1 (space)
    # + 1 to all windows so we can write at mainwinw
    mainwin = curses.newwin(mainwinh, mainwinw+1, mainwiny, mainwinx)
    mainpan = curses.panel.new_panel(mainwin)

    headerwin = curses.newwin(1, mainwinw+1, 1, mainwinx)
    headerpan = curses.panel.new_panel(headerwin)

    totalwin = curses.newwin(2, mainwinw+1, scrh-4, mainwinx)
    totalpan = curses.panel.new_panel(totalwin)

    statuswin = curses.newwin(1, mainwinw+1, scrh-2, mainwinx)
    statuspan = curses.panel.new_panel(statuswin)
    mainwin.scrollok(0)
    headerwin.scrollok(0)
    totalwin.scrollok(0)
    statuswin.addstr(0, 0, 'window resize: %s x %s' % (scrw, scrh))
    statuswin.scrollok(0)
    prepare_display()

if __name__ == '__main__':
    if (len(argv) < 2):
        print """Usage: btlaunchmanycurses.py <directory> <global options>
  <directory> - directory to look for .torrent files (non-recursive)
  <global options> - options to be applied to all torrents (see btdownloadheadless.py)
"""
        exit(-1)
    dietrace = 0
    try: 
        import curses
        import curses.panel
        scrwin = curses.initscr()
        curses.noecho()
        curses.cbreak()
    except:
        print 'Textmode GUI initialization failed, cannot proceed.'
        exit(-1)
    try:
        signal(SIGWINCH, winch_handler)
        ### Curses Setup
        scrh, scrw = scrwin.getmaxyx()
        scrpan = curses.panel.new_panel(scrwin)
        mainwinh = scrh - 5  # - 2 (bars) - 1 (debugwin) - 1 (borderwin) - 1 (totalwin)
        mainwinw = scrw - 4  # - 2 (bars) - 2 (spaces)
        mainwiny = 2         # + 1 (bar) + 1 (titles)
        mainwinx = 2         # + 1 (bar) + 1 (space)
        # + 1 to all windows so we can write at mainwinw
        mainwin = curses.newwin(mainwinh, mainwinw+1, mainwiny, mainwinx)
        mainpan = curses.panel.new_panel(mainwin)

        headerwin = curses.newwin(1, mainwinw+1, 1, mainwinx)
        headerpan = curses.panel.new_panel(headerwin)

        totalwin = curses.newwin(2, mainwinw+1, scrh-4, mainwinx)
        totalpan = curses.panel.new_panel(totalwin)

        statuswin = curses.newwin(1, mainwinw+1, scrh-2, mainwinx)
        statuspan = curses.panel.new_panel(statuswin)
        mainwin.scrollok(0)
        headerwin.scrollok(0)
        totalwin.scrollok(0)
        statuswin.addstr(0, 0, 'btlaunchmany started')
        statuswin.scrollok(0)
        prepare_display()
        displaykiller = Event()
        displaythread = Thread(target = display_thread, name = 'display', args = [displaykiller, mainquitflag])
        displaythread.setDaemon(1)
        displaythread.start()
        dropdir_mainloop(argv[1], argv[2:])
    except KeyboardInterrupt: 
        cleanup_and_quit()
    except:
        dietrace = traceback
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    if dietrace != 0:
        dietrace.print_exc()
