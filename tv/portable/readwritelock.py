# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import threading
class ReadWriteLockDummy:
    def __init__ (self):
        self.lock = threading.RLock()
    def acquire_write (self):
        self.lock.acquire()
    def acquire_read (self):
        self.lock.acquire()
    def release_write (self):
        self.lock.release()
    def release_read (self):
        self.lock.release()

class LockError:
    pass

class ReadWriteLockActual:
    def __init__ (self):
        self.lock = threading.RLock()
        self.write_cond = threading.Condition(self.lock)
        self.read_cond = threading.Condition(self.lock)
        self.write_waiting = 0
        self.read_locked = 0
        self.local = threading.local()

    def check_locals (self):
        try:
            self.local.read_locked
        except:
            # print "Initialize read_locked"
            self.local.read_locked = 0
        try:
            self.local.write_locked
        except:
            # print "Initialize write_locked"
            self.local.write_locked = 0

    def printout (self):
#        print "read_locked:", self.read_locked
#        print "local read_locked:", self.local.read_locked
#        print "local write_locked:", self.local.write_locked
        pass

    def acquire_write (self):
#        print "attempt to acquire write: ", threading.currentThread()
        self.lock.acquire()
#        print "acquire write: ", threading.currentThread()
        self.check_locals()
        if self.local.write_locked == 0:
            self.read_locked = self.read_locked - self.local.read_locked
#            if (self.local.read_locked != 0):
#                raise LockError()
            self.write_waiting = self.write_waiting + 1
            while self.read_locked > 0:
                self.write_cond.wait()
            self.write_waiting = self.write_waiting - 1
        self.local.write_locked = self.local.write_locked + 1
        self.printout()

    def release_write (self):
#        print "release write: ", threading.currentThread()
        self.check_locals()
        self.local.write_locked = self.local.write_locked - 1
        if self.local.write_locked == 0:
            self.read_locked = self.read_locked + self.local.read_locked
            if (self.write_waiting > 0):
                self.write_cond.notify()
            else:
                self.read_cond.notifyAll()
        self.printout()
        self.lock.release()

    def acquire_read (self):
#        print "attempt to acquire read: ", threading.currentThread()
        self.lock.acquire()
#        print "acquire read: ", threading.currentThread()
        self.check_locals()
        if self.local.write_locked == 0:
            if self.local.read_locked == 0:
                while self.write_waiting > 0:
                    self.read_cond.wait()
            self.read_locked = self.read_locked + 1
        self.local.read_locked = self.local.read_locked + 1
        self.printout()
        self.lock.release()
        
    def release_read (self):
#        print "attempt to release read: ", threading.currentThread()
        self.lock.acquire()
#        print "release read: ", threading.currentThread()
        self.check_locals()
        if self.local.write_locked == 0:
            self.read_locked = self.read_locked - 1
            if (self.read_locked == 0):
                self.write_cond.notify()
        self.local.read_locked = self.local.read_locked - 1
        self.printout()
        self.lock.release()

ReadWriteLock = ReadWriteLockActual
