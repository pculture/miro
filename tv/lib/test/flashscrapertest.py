from miro import flashscraper

from miro.test.framework import EventLoopTest, uses_httpclient

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

    def scrape_callback(self, new_url, content_type=None, title=None):
        self._response = (new_url, content_type, title)
        self.stopEventLoop(abnormal=False)

    @uses_httpclient
    def test_scrape(self):
        flashscraper.try_scraping_url(
            u"http://www.youtube.com/watch?v=3DTKMp24c0s",
            self.scrape_callback)
        self.run_event_loop()
        # print self._response

class VimeoScraper(FlashScraperBase):
    def setUp(self):
        FlashScraperBase.setUp(self)
        self._response = None

    def scrape_callback(self, new_url, content_type=None, title=None):
        self._response = (new_url, content_type, title)
        self.stopEventLoop(abnormal=False)

    @uses_httpclient
    def test_scrape(self):
        flashscraper.try_scraping_url(
            u'http://vimeo.com/42231616',
            self.scrape_callback)
        self.run_event_loop()
        self.assertNotEqual(self._response, None)
        self.assertNotEqual(self._response[0], None)
        self.assertEqual(type(self._response[1]), unicode)
        self.assertEqual(self._response[1], u'video/mp4')

    @uses_httpclient
    def test_scrape_moogaloop(self):
        flashscraper.try_scraping_url(
            u'http://vimeo.com/moogaloop.swf?clip_id=42231616',
            self.scrape_callback)
        self.run_event_loop()
        self.assertNotEqual(self._response, None)
        self.assertNotEqual(self._response[0], None)
        self.assertEqual(type(self._response[1]), unicode)
        self.assertEqual(self._response[1], u'video/mp4')
