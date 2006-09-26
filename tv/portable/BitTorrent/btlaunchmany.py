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
import traceback

def fmttime(n):
    if n == -1:
        return '(no seeds?)'
    if n == 0:
        return 'complete'
    n = int(n)
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    if h > 1000000:
        return 'n/a'
    return '%d:%02d:%02d' % (h, m, s)

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
print 'btlaunchmany starting..'
filecheck = Lock()

def dropdir_mainloop(d, params):
    deadfiles = []
    global threads, status
    while 1:
        files = listdir(d)
        # new files
        for file in files: 
            if file[-len(ext):] == ext:
                if file not in threads.keys() + deadfiles:
                    threads[file] = {'kill': Event(), 'try': 1}
                    print 'New torrent: %s' % file
                    stdout.flush()
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
                # if it was checking the file, it isn't anymore.
                if threadinfo.get('checking', None):
                    filecheck.release()
                if threadinfo.get('try') == 6: 
                    # Died on the sixth try? You're dead.
                    deadfiles.append(file)
                    print '%s died 6 times, added to dead list' % fil
                    stdout.flush()
                    del threads[file]
                else:
                    del threadinfo['thread']
                    threadinfo['timeout'] = 10
            # dealing with files that dissapear
            if file not in files:
                print 'Torrent file dissapeared, killing %s' % file
                stdout.flush()
                if threadinfo.get('timeout', -1) == -1:
                    threadinfo['kill'].set()
                    threadinfo['thread'].join()
                # if this thread was filechecking, open it up
                if threadinfo.get('checking', None): 
                    filecheck.release()
                del threads[file]
        for file in deadfiles:
            # if the file dissapears, remove it from our dead list
            if file not in files: 
                deadfiles.remove(file)
        sleep(1)

def display_thread(displaykiller):
    interval = 1.0
    global threads, status
    while 1:
        # display file info
        if (displaykiller.isSet()): 
            break
        totalup = 0
        totaldown = 0
        totaluptotal = 0.0
        totaldowntotal = 0.0
        for file, threadinfo in threads.items(): 
            uprate = threadinfo.get('uprate', 0)
            downrate = threadinfo.get('downrate', 0)
            uptxt = fmtsize(uprate, padded = 0)
            downtxt = fmtsize(downrate, padded = 0)
            uptotal = threadinfo.get('uptotal', 0.0)
            downtotal = threadinfo.get('downtotal', 0.0)
            uptotaltxt = fmtsize(uptotal, baseunit = 2, padded = 0)
            downtotaltxt = fmtsize(downtotal, baseunit = 2, padded = 0)
            filename = threadinfo.get('savefile', file)
            if threadinfo.get('timeout', 0) > 0:
                trys = threadinfo.get('try', 1)
                timeout = threadinfo.get('timeout')
                print '%s: try %d died, retry in %d' % (filename, trys, timeout)
            else:
                status = threadinfo.get('status','')
                print '%s: Spd: %s/%s Tot: %s/%s [%s]' % (filename, uptxt, downtxt, uptotaltxt, downtotaltxt, status)
            totalup += uprate
            totaldown += downrate
            totaluptotal += uptotal
            totaldowntotal += downtotal
        # display totals line
        totaluptxt = fmtsize(totalup, padded = 0)
        totaldowntxt = fmtsize(totaldown, padded = 0)
        totaluptotaltxt = fmtsize(totaluptotal, baseunit = 2, padded = 0)
        totaldowntotaltxt = fmtsize(totaldowntotal, baseunit = 2, padded = 0)
        print 'All: Spd: %s/%s Tot: %s/%s' % (totaluptxt, totaldowntxt, totaluptotaltxt, totaldowntotaltxt)
        print
        stdout.flush()
        sleep(interval)

class StatusUpdater:
    def __init__(self, file, params, name):
        self.file = file
        self.params = params
        self.name = name
        self.myinfo = threads[name]
        self.done = 0
        self.checking = 0
        self.activity = 'starting'
        self.display()
        self.myinfo['errors'] = []

    def download(self): 
        download(self.params + ['--responsefile', self.file], self.choose, self.display, self.finished, self.err, self.myinfo['kill'], 80)
        print 'Torrent %s stopped' % self.file
        stdout.flush()

    def finished(self): 
        self.done = 1
        self.myinfo['done'] = 1
        self.activity = 'complete'
        self.display({'fractionDone' : 1})

    def err(self, msg): 
        self.myinfo['errors'].append(msg)
        self.display()

    def failed(self): 
        self.activity = 'failed' 
        self.display() 

    def choose(self, default, size, saveas, dir):
        self.myinfo['downfile'] = default
        self.myinfo['filesize'] = fmtsize(size)
        if saveas == '': 
            saveas = default
        # it asks me where I want to save it before checking the file.. 
        self.myinfo['savefile'] = self.file[:-len(ext)]
        if exists(self.file[:-len(ext)]) and (getsize(self.file[:-len(ext)]) > 0):
            # file will get checked
            while (not filecheck.acquire(0) and not self.myinfo['kill'].isSet()):
                self.myinfo['status'] = 'disk wait'
                sleep(0.1)
            if not self.myinfo['kill'].isSet():
                self.myinfo['checking'] = 1
                self.checking = 1
        return self.file[:-len(ext)]
    
    def display(self, dict = {}):
        fractionDone = dict.get('fractionDone', None)
        timeEst = dict.get('timeEst', None)
        activity = dict.get('activity', None) 
        global status
        if activity is not None and not self.done: 
            if activity == 'checking existing file':
                self.activity = 'disk check'
            elif activity == 'connecting to peers':
                self.activity = 'connecting'
            else:
                self.activity = activity
        elif timeEst is not None: 
            self.activity = fmttime(timeEst)
        if fractionDone is not None: 
            self.myinfo['status'] = '%s %.0f%%' % (self.activity, fractionDone * 100)
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

if __name__ == '__main__':
    if (len(argv) < 2):
        print """Usage: btlaunchmany.py <directory> <global options>
  <directory> - directory to look for .torrent files (non-recursive)
  <global options> - options to be applied to all torrents (see btdownloadheadless.py)
"""
        exit(-1)
    try:
        displaykiller = Event()
        displaythread = Thread(target = display_thread, name = 'display', args = [displaykiller])
        displaythread.start()
        dropdir_mainloop(argv[1], argv[2:])
    except KeyboardInterrupt: 
        print '^C caught! Killing torrents..'
        for file, threadinfo in threads.items(): 
            status = 'Killing torrent %s' % file
            threadinfo['kill'].set() 
            threadinfo['thread'].join() 
            del threads[file]
        displaykiller.set()
        displaythread.join()
    except:
        traceback.print_exc()
