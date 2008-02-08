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

"""This module provides IdleNotifier objects which run in the background and 
   notify delegate objects about the system idle state. The low-level platform
   specific code which checks the actual idle state must be provided by the
   frontend.
   
   An IdleNotifier object is controlled by two parameters: the idle threshold
   and the periodicity. The periodicity value specifies the frequency at which
   the system's idle state will be checked. When the system has been idling for 
   more than idleThreshold seconds, the delegate's systemHasBeenIdlingSince 
   method is called. When the system is active and is known to have been 
   previously idling, the delegate's systemIsActiveAgain method is called.
"""

import time

import eventloop
import idletime
import logging

DEFAULT_PERIODICITY = 5             # Check every X seconds
DEFAULT_IDLE_THRESHOLD = 60 * 5     # Notify after X seconds of idling


class IdleNotifier:
    def __init__(self, delegate, idleThreshold=DEFAULT_IDLE_THRESHOLD, periodicity=DEFAULT_PERIODICITY):
        """Initialize the IdleNotifier object, the passed delegate will be
           called when the system idle state changes.
           - idleThreshold specifies the idle time (in seconds) after which the
           delegate is called.
           - periodicity specifies that that the idle state should be checked
           every X seconds.
        """
        self.idling = False
        self.wasIdling = False
        self.delegate = delegate
        self.idleThreshold = idleThreshold
        self.periodicity = periodicity
        self.lastTimeout = None

    def start(self):
        logging.info ("idle notifier running")
        self.lastTimeout = eventloop.addTimeout(self.periodicity,self.run,"Idle notifier")

    def run(self):
        try:
            seconds = int(idletime.get())
        except:
            logging.warning ("idletime module returned an invalid value...")
            seconds = 0.0

        if self.idling:
            self._whenIdling(seconds)
        else:
            self._whenNotIdling(seconds)
        self.lastTimeout = eventloop.addTimeout(self.periodicity,self.run,"Idle notifier")


    def join(self):
        try:
            self.lastTimeout.cancel()
        except:
            pass
    
    def _whenNotIdling(self, seconds):
        if seconds >= self.idleThreshold:
            logging.info ("system has been idling since %d seconds", seconds)
            self.idling = True
            self.wasIdling = True
            if self.delegate is not None and hasattr(self.delegate, 'systemHasBeenIdlingSince'):
                self.delegate.systemHasBeenIdlingSince(seconds)

    def _whenIdling(self, seconds):
        if seconds < self.idleThreshold:
            self.idling = False
            if self.wasIdling:
                logging.info ("system is active again since %d seconds", seconds)
                if self.delegate is not None and hasattr(self.delegate, 'systemIsActiveAgain'):
                    self.delegate.systemIsActiveAgain()
                    self.wasIdling = False
