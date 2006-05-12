import socket
import errno
from urlparse import urlparse

import config
import downloader
import eventloop
import util

class NetworkBuffer(object):
    """Responsible for storing incomming network data and doing some basic
    parsing of it.  I think this is about as fast as we can do things in pure
    python, someday we may want to make it C...
    """
    def __init__(self):
        self.chunks = []
        self.length = 0

    def addData(self, data):
        self.chunks.append(data)
        self.length += len(data)

    def _mergeChunks(self):
        self.chunks = [''.join(self.chunks)]

    def read(self, size=None):
        """Read at most size bytes from the data that has been added to the
        buffer.  """

        self._mergeChunks()
        if size is not None:
            rv = self.chunks[0][:size]
            self.chunks[0] = self.chunks[0][len(rv):]
        else:
            rv = self.chunks[0]
            self.chunks = []
        self.length -= len(rv)
        return rv

    def readline(self, sep='\r\n'):
        """Like a file readline, with two difference:  If there isn't a full
        line ready to be read we return None.  Also, if there is a line, we
        don't include the trailing line separator.
        """

        self._mergeChunks()
        split = self.chunks[0].split(sep, 1)
        if len(split) == 2:
            self.chunks[0] = split[1]
            self.length = len(self.chunks[0])
            return split[0]
        else:
            return None

    def unread(self, data):
        """Put back read data.  This make is like the data was never read at
        all.
        """
        self.chunks.insert(0, data)
        self.length += len(data)

    def printout(self):
        self._mergeChunks()
        print self.chunks[0]

class ConnectionHandler(object):
    """Base class to handle socket connections.  It's a thin wrapper our now
    fangled asynchronous eventloop module to make it easier to deal with
    protocols.

    Subclasses can use sendData to write data out to the socket and use
    startReading() to signal that they are ready to handle data coming in.  

    Subclasses should override the handleData() method, which handles chunks
    of data as it becomes available on the socket.  Also the handleClose()
    method to handle the socket closing.
     """

    def __init__(self):
        self.toSend = ''
        self.connected = False
        self.readSize = 4096

    def openConnection(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(0)
        rv = self.socket.connect_ex((host, port))
        if rv not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
            raise socket.error, (rv, errno.errorcode[rv])
        self.connected = True

    def closeConnection(self):
        if self.connected:
            eventloop.stopHandlingSocket(self.socket)
            self.socket.shutdown(socket.SHUT_RDWR)
            self.connected = False
            self.socket = None
            self.state = 'closed'

    def sendData(self, data):
        self.toSend += data
        eventloop.addWriteCallback(self.socket, self.writeCallback)

    def writeCallback(self):
        sent = self.socket.send(self.toSend)
        if sent == 0:
            self.handleClose(socket.SHUT_WR)
        self.toSend = self.toSend[sent:]
        if self.toSend == '':
            eventloop.removeWriteCallback(self.socket)

    def startReading(self):
        eventloop.addReadCallback(self.socket, self.readCallback)

    def stopReading(self):
        eventloop.removeReadCallback(self.socket, self.readCallback)

    def readCallback(self):
        data = self.socket.recv(self.readSize)
        if data == '':
            self.handleClose(socket.SHUT_RD)
        else:
            self.handleData(data)

    def handleClose(self, type):
        """Handle the socket becoming closed.  Type is either socket.SHUT_RD,
        or socket.SHUT_WR.
        """
        raise NotImplementError()

    def handleData(self, data):
        """Handle a chunk of data coming in from the wire"""
        raise NotImplementError()

class HTTPError(Exception):
    pass

class BadStatusLine(HTTPError):
    pass

class BadHeaderLine(HTTPError):
    pass

class ServerClosedConnection(HTTPError):
    pass

class HTTPRequest(ConnectionHandler):
    MAX_REDIRECTIONS = 10
    MAX_AUTH_REQUEST = 5
    USER_AGENT = "%s/%s (%s)" % \
            (config.get(config.SHORT_APP_NAME),
             config.get(config.APP_VERSION),
             config.get(config.PROJECT_URL))
    READ_SIZE = 8192

    def __init__(self, host, port, callback, errback):
        super(HTTPRequest, self).__init__()
        self.callback = callback
        self.errback = errback
        self.host = host
        self.port = port
        self.startNewResponse()
        self.buffer = NetworkBuffer()
        self.openConnection(self.host, self.port)
        self.shortVersion = 0
        self.state = 'ready'
        self.unparsedHeaderLine = ''

    def sendRequest(self, method="GET", path='/', headers=None):
        self.method = method
        self.path = path
        # Figure out what headers we will send
        self.requestHeaders = {
            'User-Agent': self.USER_AGENT,
            'Host': self.host.encode('idna'),
            'Accept-Encoding': 'identity',
        }
        if headers is not None:
            self.requestHeaders.update(headers)
        self.sendData(self.formatRequest())
        self.state = "response-status"
        self.startReading()

    def startNewResponse(self):
        self.version = None
        self.status = None
        self.reason = None
        self.headers = {}
        self.body = None
        self.expectedLength = None
        self.willClose = None

    def formatRequest(self):
        sendOut = []
        sendOut.append('%s %s HTTP/1.1\r\n' % (self.method, self.path))
        for header, value in self.requestHeaders.items():
            sendOut.append('%s: %s\r\n' % (header, value))
        sendOut.append('\r\n')
        return ''.join(sendOut)
        
    def handleData(self, data):
        self.buffer.addData(data)
        if self.state == "response-status":
            line = self.buffer.readline()
            if line is not None:
                self.handleStatusLine(line)
                if self.shortVersion != 9:
                    self.state = 'response-headers'
                else:
                    self.headersDone()
        if self.state == "response-headers":
            line = self.buffer.readline()
            while line is not None:
                self.handleHeaderLine(line)
                if self.state == 'response-headers':
                    line = self.buffer.readline()
                else:
                    break
        if self.state == 'response-body':
            if (self.expectedLength is not None and 
                    self.buffer.length >= self.expectedLength):
                self.body = self.buffer.read(self.expectedLength)
                self.sendCallback()
                self.state = 'ready'

    def handleStatusLine(self, line):
        try:
            (version, status, reason) = line.split(None, 2)
        except ValueError:
            try:
                (version, status) = line.split(None, 1)
                reason = ""
            except ValueError:
                # empty version will cause next test to fail and status
                # will be treated as 0.9 response.
                version = ""
        if not version.startswith('HTTP/'):
            # assume it's a Simple-Response from an 0.9 server
            self.buffer.unread(line + '\r\n')
            self.version = "HTTP/0.9"
            self.status = 200
            self.reason = ""
            self.shortVersion = 9
        else:
            try:
                status = int(status)
                if status < 100 or status > 599:
                    self.handleError(BadStatusLine(line))
                    return
            except ValueError:
                self.handleError(BadStatusLine(line))
                return
            if version == 'HTTP/1.0':
                self.shortVersion = 10
            elif version.startswith('HTTP/1.'):
                # use HTTP/1.1 code for HTTP/1.x where x>=1
                self.shortVersion = 11
            else:
                self.handleError(BadStatusLine(line))
                return
            self.version = version
            self.status = status
            self.reason = reason

    def handleHeaderLine(self, line):
        if self.unparsedHeaderLine == '':
            if line == '':
                self.headersDone()
            elif ':' in line:
                self.parseHeader(line)
            else:
                self.unparsedHeaderLine = line
        else:
            # our last line may have been a continued header, or it may be
            # garbage, 
            if len(line) > 0 and line[0] in (' ', '\t'):
                self.unparsedHeaderLine += line.lstrip()
                if ':' in self.unparsedHeaderLine:
                    self.parseHeader(self.unparsedHeaderLine)
                    self.unparsedHeaderLine = ''
            else:
                msg = "line: %s, next line: %s" % (self.unparsedHeaderLine, 
                        line)
                self.handleError(BadHeaderLine(msg))

    def parseHeader(self, line):
        header, value = line.split(":", 1)
        value = value.strip()
        header = header.lstrip().lower()
        if value == '':
            self.handleError(BadHeaderLine(line))
            return
        if header not in self.headers:
            self.headers[header] = value
        else:
            self.headers[header] += (',%s' % value)

    def headersDone(self):
        if ((100 <= self.status <= 199) or self.status in (204, 304) or
                self.method == 'HEAD'):
            self.state = 'ready'
        else:
            self.state = 'response-body'
            self.findExpectedLength()
            self.decideWillClose()

    def findExpectedLength(self):
        if self.headers.get('transfer-encoding') != 'identity':
            try:
                self.expectedLength = int(self.headers['content-length'])
            except (ValueError, KeyError):
                pass
            if self.expectedLength < 0:
                self.expectedLength = None

    def decideWillClose(self):
        # this was basically ripped out from httplib.HTTPConnection
        if 'close' in self.headers.get('connection', ''):
            self.willClose = True
        elif self.version == 11:
            self.willClose = False
        elif 'keep-alive' in self.headers:
            # For older HTTP, Keep-Alive indiciates persistent connection.
            self.willClose = False
        elif 'keep-alive' in self.headers.get('connection', ''):
            # At least Akamai returns a "Connection: Keep-Alive" header, which
            # was supposed to be sent by the client.
            self.willClose = False
        elif "keep-alive" in self.headers.get('proxy-connection', '').lower():
            # Proxy-Connection is a netscape hack.
            self.willClose = False
        else:
            # otherwise, assume it will close
            return True

    def sendCallback(self):
        response = {
            'version': self.version,
            'status': self.status,
            'reason': self.reason,
            'headers': self.headers,
            'body': self.body,
        }
        try:
            self.callback(response)
        except:
            util.failedExn("While talking to the network")
            self.closeConnection()
        
    def handleClose(self, type):
        self.closeConnection()
        if self.state == 'response-body':
            if self.expectedLength is None:
                self.body = self.buffer.read()
                self.sendCallback()
            elif self.expectedLength >= self.buffer.length:
                self.body = self.buffer.read(self.expectedLength)
                self.sendCallback()
            else:
                self.errback(ServerClosedConnection())

        else:
            self.errback(ServerClosedConnection())

    def handleError(self, error):
        self.closeConnection()
        self.errback(error)

    def NOTDONEYET():
        download = connectionPool.getRequest(scheme,host,type, path, headers = myHeaders)

        if download is None:
            return None

        #print "Got it!"
        depth = 0
        authAttempts = 0
        while ((download.status != 304) and
               ((start == 0 and download.status != 200) or
                (start > 0 and download.status != 206)) and 
               (depth < maxDepth and authAttempts < maxAuthAttempts)):
            if download.status == 302 or download.status == 307 or download.status == 301:
                #print " redirect"
                depth += 1
                info = download.msg
                download.close()
                if info.has_key('location'):
                    redirURL = urljoin(redirURL,info['location'])
                if download.status == 301:
                    url = redirURL
                (scheme, host, path, params, query, fragment) = parseURL(redirURL)

                try:
                    del myHeaders["Authorization"]
                except KeyError:
                    pass
                auth = findHTTPAuth(host,path)
                if not auth is None:
                    #print " adding auth header"
                    myHeaders["Authorization"] = auth.getAuthScheme()+' '+auth.getAuthToken()

                if len(params):
                    path += ';'+params
                if len(query):
                    path += '?'+query
                #print "getURLInfo Redirected to "+host
                download = connectionPool.getRequest(scheme,host,type,path, headers=myHeaders)
                if download is None:
                    return None
            elif download.status == 401:
                if download.msg.has_key('WWW-Authenticate'):
                    authAttempts += 1
                    info = download.msg
                    download.close()
                    regExp = re.compile("^(.*?)\s+realm\s*=\s*\"(.*?)\"$").search(info['WWW-Authenticate'])
                    authScheme = regExp.expand("\\1")
                    realm = regExp.expand("\\2")
                    #print "Trying to authenticate "+host+" realm:"+realm
                    result = delegate.getHTTPAuth(host,realm)
                    if not result is None:
                        import downloader
                        auth = downloader.HTTPAuthPassword(result[0],result[1],host, realm, path, authScheme)
                        myHeaders["Authorization"] = auth.getAuthScheme()+' '+auth.getAuthToken()
                        download = connectionPool.getRequest(scheme,host,type,path, headers=myHeaders)
                    else:
                        return None #The user hit Cancel

                    #This is where we would do our magic to prompt for a password
                    #If we get a good password, we save it
                else:
                    break
            else: #Some state we don't handle
                break

        # Valid or cached pages
        if not download.status in [200,206,304]:
            return None

        #print "processing request"
        info = download.msg
        myInfo = {}
        for key in info.keys():
            myInfo[key] = info[key]
        info = myInfo
        if type == 'GET':
            info['file-handle'] = download
        else:
            download.close()
        #print "closed request"

        info['filename'] = 'unknown'
        try:
            disposition = info['content-disposition']
            info['filename'] = re.compile("^.*filename\s*=\s*\"(.*?)\"$").search(disposition).expand("\\1")
            info['filename'] = cleanFilename(info['filename'])
        except:
            try:
                info['filename'] = re.compile("^.*?([^/]+)/?$").search(path).expand("\\1")
                info['filename'] = cleanFilename(info['filename'])
            except:
                pass

        info['redirected-url'] = redirURL
        info['updated-url'] = url
        info['status'] = download.status
        try:
            info['charset'] = re.compile("^.*charset\s*=\s*(\S+)/?$").search(info['content-type']).expand("\\1")
        except (AttributeError, KeyError):
            pass
        return info

def parseURL(url):
    (scheme, host, path, params, query, fragment) = urlparse(url)
    # Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz)
    # which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    else:
        host = host
        if scheme == 'https':
            port = 443
        else:
            port = 80

    fullPath = path
    if params:
        fullPath += ';%s' % params
    if query:
        fullPath += '?%s' % query
    return scheme, host, port, fullPath

def makeRequest(url, callback, errback, method="GET", start=0, etag=None,
        modified=None, findHTTPAuth=None):
    # TODO: CONNECTION POOLS!
    scheme, host, port, path = parseURL(url)
    headers = {}

    if findHTTPAuth is None:
        findHTTPAuth = downloader.findHTTPAuth
    auth = findHTTPAuth(host, path)
    if not auth is None:
        authHeader = "%s %s" % (auth.getAuthScheme(), auth.getAuthToken())
        headers["Authorization"] = authHeader
    if start > 0:
        headers["Range"] = "bytes="+str(start)+"-"
    if not etag is None:
        headers["If-None-Match"] = etag
    if not modified is None:
        headers["If-Modified-Since"] = modified
    r = HTTPRequest(host, port, callback, errback)
    r.sendRequest(method, path, headers)
