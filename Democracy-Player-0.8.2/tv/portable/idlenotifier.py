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

import threading
import time

import idletime

DEFAULT_PERIODICITY = 5             # Check every X seconds
DEFAULT_IDLE_THRESHOLD = 60 * 5     # Notify after X seconds of idling


class IdleNotifier (threading.Thread):
    
    def __init__(self, delegate, idleThreshold=DEFAULT_IDLE_THRESHOLD, periodicity=DEFAULT_PERIODICITY):
        """Initialize the IdleNotifier object, the passed delegate will be
           called when the system idle state changes.
           - idleThreshold specifies the idle time (in seconds) after which the
           delegate is called.
           - periodicity specifies that that the idle state should be checked
           every X seconds.
        """
        threading.Thread.__init__(self)
        self.setName("IdleNotifier")
        self.setDaemon(True)
        self.stopEvent = threading.Event()
        self.idling = False
        self.wasIdling = False
        self.delegate = delegate
        self.idleThreshold = idleThreshold
        self.periodicity = periodicity
                        
    def run(self):
        print "DTV: idle notifier thread running"
        while not self.stopEvent.isSet():
            seconds = idletime.get()
            if self.idling:
                self._whenIdling(seconds)
            else:
                self._whenNotIdling(seconds)
            self.stopEvent.wait(self.periodicity)
        print "DTV: idle notifier thread stopped"

    def join(self):
        self.stopEvent.set()
        threading.Thread.join(self)
    
    def _whenNotIdling(self, seconds):
        if seconds >= self.idleThreshold:
            print "DTV: system has been idling since %d seconds" % seconds
            self.idling = True
            self.wasIdling = True
            if self.delegate is not None and hasattr(self.delegate, 'systemHasBeenIdlingSince'):
                self.delegate.systemHasBeenIdlingSince(seconds)

    def _whenIdling(self, seconds):
        if seconds < self.idleThreshold:
            self.idling = False
            if self.wasIdling:
                print "DTV: system is active again since %d seconds" % seconds
                if self.delegate is not None and hasattr(self.delegate, 'systemIsActiveAgain'):
                    self.delegate.systemIsActiveAgain()
                    self.wasIdling = False
