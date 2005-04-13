from threading import Timer,currentThread
from database import DynamicDatabase,DDBObject
from time import time

def now():
    return int(time())
##
# Database of background tasks to be periodically run
class Scheduler(DynamicDatabase):
    def __init__(self):
        DynamicDatabase.__init__(self)
        self.timer = Timer(2000000000,self.executeEvents)
        self.timer.setDaemon(True)
        self.timer.start()
        self.timer.cancel()
        self.timer.join()
        self.updateInterval()
        
    ##
    # Determines when we next need to update and sets the timer appropriately
    def updateInterval(self):
        self.beginUpdate()
        try:
            self.timer.cancel()
            if self.timer != currentThread():
                self.timer.join()
            if self.len() > 0:
                nextRun = 2000000000
                self.resetCursor()
                for event in self:
                    nextRun = min(nextRun,event.nextRun())
                if nextRun <= 0:
                    self.executeEvents()
                    self.updateInterval()
                else:
                    self.timer = Timer(nextRun,self.executeEvents)
                    self.timer.setDaemon(True)
                    self.timer.start()
        finally:
            self.endUpdate()

    ##
    # Executes all pending events
    def executeEvents(self):
        self.beginUpdate()
        try:
            self.resetCursor()
            for event in self:
                if event.nextRun() <= 0:
                    event.execute()
            self.updateInterval()
        finally:
            self.endUpdate()
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
        self.dd.updateInterval()

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
    # Removes the object from the scheduler, then recalculates the
    # update interval based on the new list of events7
    def remove(self):
        self.dd.beginUpdate()
        try:
            DDBObject.remove(self)
            self.dd.updateInterval()
        finally:
            self.dd.endUpdate()
    ##
    # Makes an event happen
    def execute(self):
        self.scheduler.beginUpdate()
        try:
            self.event()
            self.lastRun = now()
            if not self.repeat:
                self.remove()
        finally:
            self.scheduler.endUpdate()
