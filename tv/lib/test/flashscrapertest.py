from miro import flashscraper

from miro.test.framework import EventLoopTest

class FlashScraperBase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.event_loop_timeout = 20
        self.start_http_server()

    def run_event_loop(self, timeout=None):
        if timeout == None:
            timeout = self.event_loop_timeout
        EventLoopTest.runEventLoop(self, timeout=timeout)

    def tearDown(self):
        EventLoopTest.tearDown(self)
        self.stopEventLoop(abnormal=False)

class YouTubeScraper(FlashScraperBase):
    # this is super helpful if you set logging to DEBUG.  then you can
    # debug youtube flashscraper issues from here.
    def setUp(self):
        FlashScraperBase.setUp(self)
        self._response = None

    def scrape_callback(self, new_url, contentType=None, title=None):
        self._response = (new_url, contentType, title)
        self.stopEventLoop(abnormal=False)

    def test_scrape(self):
        flashscraper.try_scraping_url(
            u"http://www.youtube.com/watch?v=3DTKMp24c0s",
            self.scrape_callback)
        self.run_event_loop()
        # print self._response
