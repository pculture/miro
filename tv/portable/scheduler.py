from threading import Timer, currentThread, RLock, Thread
from database import DynamicDatabase,DDBObject
from time import time

def now():
    return int(time())
##
# Database of background tasks to be periodically run
class Scheduler(DynamicDatabase):
    def __init__(self):
        DynamicDatabase.__init__(self)
        self.timer = Timer(1,self.executeEvents)
	self.lock = RLock()
	self.timer.start()
        
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
    # Executes all pending events
    def executeEvents(self):
	self.resetCursor()
	self.beginUpdate()
	try:
	    for event in self:
		if event.nextRun() <= 0:
		    event.lastRun = now()
		    if not event.repeat:
			event.remove()
		    t = Thread(target = event.execute)
		    t.start()
	finally:
	    self.endUpdate()
	self.timer.cancel()
	self.timer = Timer(1,self.executeEvents)
	self.timer.start()

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

