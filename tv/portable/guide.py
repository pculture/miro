from database import DDBObject
from downloader import grabURL
from scheduler import ScheduleEvent
from xhtmltools import urlencode
from copy import copy

class ChannelGuide(DDBObject):
    def __init__(self):
        self.html = '<h1>Welcome to DTV</h1><p>blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah blah</p>'
        self.viewed = False
        ScheduleEvent(3600,self.update,True)
        DDBObject.__init__(self)

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        self.__dict__ = data
        ScheduleEvent(0,self.update,False)
        ScheduleEvent(3600,self.update,True)


    def getHTML(self):
        if not self.viewed:
            html = self.html
            ScheduleEvent(0,self.update,False)
            self.viewed = True
            return html
        else:
            return self.html

    def update(self):
        # We grab the URL and convert the HTML to JavaScript so it can
        # be loaded from a plain old template. It's less elegant than
        # making another kind of feed object, but it makes it easier
        # for non-programmers to work with
        url = 'http://clients.tekritisoftware.com/pcf/channelguide/'
        info = grabURL(url)
        html = "<script type=\"text/javascript\">"
        lines = info['file-handle'].read().split("\n")
        try:
            for line in lines:
                html = "%sdocument.writeln(unescape(\"%s\"));\n" % (html,urlencode(line.replace("\r","").replace("\n","")))
        except:
            print 'DTV: channel guide load failed'
            return
        info['file-handle'].close()
        html = "%s\n</script>" % html
        self.html = html
