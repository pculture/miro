from threading import RLock, Thread
from database import DynamicDatabase,DDBObject
from time import time, sleep

def now():
    return int(time())
##
# Database of background tasks to be periodically run
class Scheduler(DynamicDatabase):
    def __init__(self):
        DynamicDatabase.__init__(self)
        self.isShutdown = False
	self.lock = RLock()
        self.thread = Thread(target = self.executeEvents)
	self.thread.setDaemon(False)
	self.thread.start()

    ##
    # Scheduler uses it's own lock
    def beginUpdate(self):
	self.lock.acquire()
    def endUpdate(self):
	self.lock.release()
    def beginRead(self):
	self.lock.acquire()
    def endRead(self):
	self.lock.release()

    ##
    # Call this to shutdown the scheduler
    def shutdown(self):
	self.isShutdown = True
	
    ##
    # Executes all pending events
    def executeEvents(self):
	while not self.isShutdown:
	    self.beginUpdate()
	    try:
		self.resetCursor()
		for event in self:
		    if event.nextRun() <= 0:
			event.lastRun = now()
			if not event.repeat:
			    event.remove()
			t = Thread(target = event.execute)
			t.setDaemon(False)
			t.start()
	    finally:
		self.endUpdate()
	    sleep(1)
##
# a ScheduleEvent corresponds to something that happens in the
# future, possibly periodically

class ScheduleEvent(DDBObject):
    scheduler = Scheduler()

    ##
    # Schedules an event for interval seconds from now
    # Repeats every
    def __init__(self,interval, event, repeat = True):
        self.interval = interval
        self.event = event
        self.repeat = repeat
        self.lastRun = now()
        DDBObject.__init__(self,ScheduleEvent.scheduler)

    ##
    # Returns number of seconds until next run
    def nextRun(self):
        self.scheduler.beginRead()
        try:
            ret = self.interval + self.lastRun - now()
        finally:
            self.scheduler.endRead()
        return ret

    ##
    # Makes an event happen
    def execute(self):
	self.event()

