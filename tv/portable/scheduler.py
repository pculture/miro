from threading import Thread, Semaphore
from database import DynamicDatabase,DDBObject
from time import time, sleep
import threadpriority

def now():
    return int(time())

# This should be higher than the number of feeds and simultaneous downloads
maxThreads = 100
semaphore = Semaphore(maxThreads)

##
# Database of background tasks to be periodically run
class Scheduler(DynamicDatabase):
    def __init__(self):
        DynamicDatabase.__init__(self)
        self.isShutdown = False
        thread = Thread(target = self.executeEvents)
        thread.setName("Scheduler")
	thread.setDaemon(False)
	thread.start()

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
			t = Thread(target = event.execute,
                                   name = "Scheduler exec event")
			t.setDaemon(False)
			t.start()
	    finally:
		self.endUpdate()
	    sleep(1)

##
# a ScheduleEvent corresponds to something that happens in the
# future, possibly periodically

class ScheduleEvent(DDBObject):
    ##
    # Schedules an event for interval seconds from now
    # Repeats every
    def __init__(self,interval, event, repeat = True):
        self.interval = int(interval)
        self.event = event
        self.repeat = repeat
        self.lastRun = now()
        DDBObject.__init__(self,ScheduleEvent.scheduler)

    ##
    # Returns number of seconds until next run
    def nextRun(self):
        self.beginRead()
        try:
            ret = self.interval + self.lastRun - now()
        finally:
            self.endRead()
        return ret

    ##
    # Makes an event happen
    def execute(self):
        #print "Spawning %s" % str(self.event)

        threadpriority.setBackgroundPriority()
        semaphore.acquire()
        try:
            self.event()
        finally:
            semaphore.release()
        #print "%s finished " % str(self.event)
        threadpriority.setBackgroundPriority()
