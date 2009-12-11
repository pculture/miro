from miro.test.framework import MiroTestCase
from miro.download_utils import parse_url

class TestParseURL(MiroTestCase):
    def doCheck(self, url, scheme, host, port, path):
        result = parse_url(url)
        self.assertEquals(result[0], scheme)
        self.assertEquals(result[1], host)
        self.assertEquals(result[2], port)
        self.assertEquals(result[3], path)

    def testFileUrls(self):
        self.doCheck('file:///abc', 'file', '', None, '/abc')
        self.doCheck('file://abc', 'file', '', None, '/abc')
        self.doCheck('file:///C:\\Program%20Files', 'file', '', None, 
                'C:/Program%20Files')
        self.doCheck('file:///C:/Program%20Files', 'file', '', None, 
                'C:/Program%20Files')
        self.doCheck('file://C:/abc', 'file', '', None, 'C:/abc')
        self.doCheck('file://C|/abc', 'file', '', None, 'C:/abc')
        self.doCheck('file://abc', 'file', '', None, '/abc')

    def testHTTPUrls(self):
        self.doCheck('http://foo.com/index.html?a=3', 'http', 'foo.com', 80,
                '/index.html?a=3')
        self.doCheck('http://foo.com:123:123/', 'http', 'foo.com', 123, '/')
        self.doCheck('https://foo.com/', 'https', 'foo.com', 443, '/')
