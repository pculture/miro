import config
import re
import socket
from os import access, F_OK
from urlparse import urlparse,urljoin
from threading import RLock, Thread
from time import time
from httplib import HTTPConnection, HTTPSConnection,HTTPException
import eventloop

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

# Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz) which
# seem to be part of #441.
def parseURL(url):
    (scheme, host, path, params, query, fragment) = urlparse(url)
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]
    return (scheme, host, path, params, query, fragment)

# Returns a filename minus nasty characters
def cleanFilename(filename):
    return filename.replace("\\","").replace("/","").replace(":","").replace("*","").replace("?","").replace("\"","").replace("<","").replace(">","").replace("|","")

##
# Finds a filename that's unused and similar the the file we want
# to download
def nextFreeFilename(name):
    if not access(name,F_OK):
        return name
    parts = name.split('.')
    count = 1
    if len(parts) == 1:
        newname = "%s.%s" % (name, count)
        while access(newname,F_OK):
            count += 1
            newname = "%s.%s" % (name, count)
    else:
        insertPoint = len(parts)-1
        parts[insertPoint:insertPoint] = [str(count)]
        newname = '.'.join(parts)
        while access(newname,F_OK):
            count += 1
            parts[insertPoint] = str(count)
            newname = '.'.join(parts)
    return newname

def _grabURLThread(callback, url, name, start, etag, modified, findHTTPAuth, useRemoteConfig, getBody, args, kwargs):
    info = None
    try:
        if getBody == False:
            info = grabURL(url, "HEAD", start, etag, modified, findHTTPAuth, useRemoteConfig)
            if info == None:
                info = grabURL (url, "GET", start, etag, modified, findHTTPAuth, useRemoteConfig)
        else:
            info = grabURL(url, "GET", start, etag, modified, findHTTPAuth, useRemoteConfig)
            if info:
                info["body"] = info["file-handle"].read()
    finally:
        eventloop.addIdle (callback, "Grab URL Callback %s (%s)" % (url, name), (info,) + args, kwargs)

# args and kargs are passed directly to grabURL  Any extra args are passed to callback.
def grabURLAsync(callback, url, name, start=0, etag=None, modified=None, findHTTPAuth=None, useRemoteConfig=False, getBody=True, args = (), kwargs = {}):
    if url is None:
        eventloop.addIdle (callback, "Grab URL Callback %s (%s)" % (url, name), (None,) + args, kwargs)
        return
    request = {}
    request["callback"] = callback
    request["url"] = url
    request["name"] = name
    request["start"] = start
    request["etag"] = etag
    request["modified"] = modified
    request["findHTTPAuth"] = findHTTPAuth
    request["useRemoteConfig"] = useRemoteConfig
    request["getBody"] = getBody
    request["args"] = args
    request["kwargs"] = kwargs
    thread = Thread(target=_grabURLThread,\
                    name="grabURL",
                    kwargs=request)
    thread.setDaemon(True)
    thread.start()

# FIXME: Currently, returns a None object in the case where it can't
# download the file. In the future, we should probably raise
# exceptions for each possible failure case and catch those everywhere
# this is used.

# Given a URL returns an info object which may contain the following
# keys: content-length, accept-ranges, server, last-modified, date,
# etag, content-type, redirected-url, updated-url, file-handle
#
# redirected-url, updated-url, filename, and file-handle are generated by
# getURLInfo. All of the other information is grabbed from the actual
# HTTP headers.
#
# Currently, only GET and HEAD requests are supported
#
# File handle is passed when a GET request is made. Call read() on it
# until read() returns '', then call close(). If you do not call
# close(), the connection will never be freed up.
#
# Redirected URL is the URL actually loaded after all of the redirects.
# Updated-url is the URL of the last permanent redirect
def grabURL(url, type="GET",start = 0, etag=None,modified=None,findHTTPAuth=None, useRemoteConfig = False):
    if findHTTPAuth is None:
        import downloader
        findHTTPAuth = downloader.findHTTPAuth
    maxDepth = 10
    maxAuthAttempts = 5
    redirURL = url
    if useRemoteConfig:
        from dl_daemon import remoteconfig
        userAgent = "%s/%s (%s)" % \
                    (remoteconfig.get(config.SHORT_APP_NAME),
                     remoteconfig.get(config.APP_VERSION),
                     remoteconfig.get(config.PROJECT_URL))
    else:
        userAgent = "%s/%s (%s)" % \
                    (config.get(config.SHORT_APP_NAME),
                     config.get(config.APP_VERSION),
                     config.get(config.PROJECT_URL))
    myHeaders = {"User-Agent": userAgent}

    (scheme, host, path, params, query, fragment) = parseURL(url)
    #print "grab URL called for "+host

    auth = findHTTPAuth(host,path)
    if not auth is None:
        #print " adding auth header"
        myHeaders["Authorization"] = auth.getAuthScheme()+' '+auth.getAuthToken()

    if len(params):
        path += ';'+params
    if len(query):
        path += '?'+query

    if start > 0:
        myHeaders["Range"] = "bytes="+str(start)+"-"

    if not etag is None:
        myHeaders["If-None-Match"] = etag

    if not modified is None:
        myHeaders["If-Modified-Since"] = modified

    download = connectionPool.getRequest(scheme,host,type,path, headers = myHeaders)

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

# An HTTP response that tells the connection pool when it is free,
# so that the connection can be reused
class PooledHTTPResponse:
    def __init__(self,conn,response,connPool):
        self.conn = conn
        self.response = response
        self.connPool = connPool
        self.beenRead = False

    def read(self,amt=None):
        if amt is None:
            ret = ''
            next = self.response.read()
            while len(next) > 0:
                ret += next
                next = self.response.read()
            self.beenRead = True
        else:
            ret = self.response.read(amt)
        if ret == '':
            self.beenRead = True
        return ret

    def getheader(self,name,default = None):
        if isinstance(default, None):
            return self.response.getheader(name)
        else:
            return self.response.getheader(name,default)
        
    def getheaders(self):
        return self.response.getheaders()

    def __getattr__(self,key):
        return getattr(self.response, key)

    #
    # Use like close(), but in the middle of a download
    def kill(self):
        if not self.beenRead:
            self.connPool.removeConn(self.conn)
        else:
            self.connPool.freeConn(self.conn)

    def close(self):
        if not self.beenRead:
            #print "Closing unread response..."+str(self.response)
            try:
                out = self.response.read(8192)
                while len(out)>0:
                     #print "still closing "+str(self.response)
                    out = self.response.read(8192)
                #print "done closing"
                self.connPool.freeConn(self.conn)
            except ValueError:
                print "Caught error in httplib"
                self.connPool.removeConn(self.conn)

#
# This class a set of HTTP connections so that we always do the
# optimal thing when we need a new connection. Generally, if there's a
# free existing connection, we use that, otherwise we create a new one
#
# FIXME: add certificate validation for HTTPS
class HTTPConnectionPool:

    # The maximum number of connections we keep active. The total
    # number may exceed this, but free connections that bring the
    # total number above maxConns will be closed
    maxConns = 30
    maxConnsPerServer = 8
    connTimeout = 300
    def __init__(self):
        self.conns={'free':{'http':{},'https':{}},
                    'inuse':{'http':{},'https':{}}}
        self.lock = RLock()

    def __len__(self):
        self.lock.acquire()
        try:
            length = 0
            for state in self.conns:
                for protocol in self.conns[state]:
                    for host in self.conns[state][protocol]:
                        length += len(self.conns[state][protocol][host])
        finally:
            self.lock.release()
        return length

    # moves connection from inuse to free
    #
    # get your freeConn!
    def freeConn(self,conn):
        freed = False
        #print "Trying to free connection..."
        self.lock.acquire()
        try:
            for prot in self.conns['inuse']:
                for h in self.conns['inuse'][prot]:
                    try:
                        index = self.conns['inuse'][prot][h].index(conn)
                        del self.conns['inuse'][prot][h][index]
                        protocol = prot
                        host = h
                        freed = True
                    except ValueError:
                        pass
            if freed:
                #print "Connection to "+host+ " is idle"
                if not self.conns['free'][protocol].has_key(host):
                    self.conns['free'][protocol][host] = []
                self.conns['free'][protocol][host].append((conn, time()+self.connTimeout))
            #else:
                #print "Not freed!"
        finally:
            self.lock.release()

    #
    # Removes a connection from the pool
    def removeConn(self,conn):
        self.lock.acquire()
        try:
            for protocol in self.conns['free']:
                for host in self.conns['free'][protocol]:
                    for pair in self.conns['free'][protocol][host]:
                        if pair[0] is conn:
                            #print "Removing connection to "+host
                            self.conns['free'][protocol][host].remove(pair)
            for protocol in self.conns['inuse']:
                for host in self.conns['inuse'][protocol]:
                    for uConn in self.conns['inuse'][protocol][host]:
                        if uConn is conn:
                            #print "Removing connection to "+host
                            self.conns['inuse'][protocol][host].remove(uConn)
        finally:
            self.lock.release()
        conn.close()

    def removeOldestFreeConnection(self):
        #print "Removing oldest connection..."
        self.lock.acquire()
        try:
            conn = None
            oldest = -1
            for protocol in self.conns['free']:
                for host in self.conns['free'][protocol]:
                    for (newConn, newExp) in self.conns['free'][protocol][host]:
                        if newExp > oldest:
                            oldest = newExp
                            conn = newConn
            if not (conn is None):
                self.removeConn(conn)
        finally:
            self.lock.release()
        #print "...done"

    def removeOldestFreeByHost(self,protocol,host):
        #print "Removing oldest connection to "+host+"..."
        self.lock.acquire()
        try:
            conn = None
            oldest = -1
            for (newConn, newExp) in self.conns['free'][protocol][host]:
                if newExp > oldest:
                    oldest = newExp
                    conn = newConn
            if not (conn is None):
                self.removeConn(conn)
        finally:
            self.lock.release()
        #print "...done"
 
    def expireOldConnections(self):
        now = time()
        self.lock.acquire()
        try:
            for protocol in self.conns['free']:
                for host in self.conns['free'][protocol]:
                    for pair in self.conns['free'][protocol][host]:
                        if pair[1] <= now:
                            #print "Expiring connection to "+host
                            pair[0].close()
                            self.conns['free'][protocol][host].remove(pair)
        finally:
            self.lock.release()

    def getNumConnsByHost(self,protocol,host):
        self.lock.acquire()
        try:
            if not self.conns['free'][protocol].has_key(host):
                self.conns['free'][protocol][host] = []
            if not self.conns['inuse'][protocol].has_key(host):
                self.conns['inuse'][protocol][host] = []
            ret = (len(self.conns['inuse'][protocol][host])+
                   len(self.conns['free'][protocol][host]))
        finally:
            self.lock.release()
        return ret

    def getRequest(self,protocol,host,method,url,*args,**keywords):
        #print "Making "+protocol+" connection to "+host+"..."
        madeNewConn = False
        self.lock.acquire()
        try:
            conn = None
            self.expireOldConnections()
            if (self.conns['free'][protocol].has_key(host) and
                        len(self.conns['free'][protocol][host]) > 0):
                (conn, expiration) = self.conns['free'][protocol][host].pop(0)
                if not self.conns['inuse'][protocol].has_key(host):
                    self.conns['inuse'][protocol][host] = []
                self.conns['inuse'][protocol][host].append(conn)
                #print "Using existing connection"
        finally:
            self.lock.release()
        
        # We don't already have a connection -- get one
        if conn is None:
            madeNewConn = True
            #print "Making new connection..."
            if protocol.lower() == 'http':
                conn = HTTPConnection(host)
            elif protocol.lower() == 'https':
                conn = HTTPSConnection(host)

            #Save our newly created connection
            self.lock.acquire()
            try:   
                if not self.conns['free'][protocol].has_key(host):
                    self.conns['free'][protocol][host] = []
                if not self.conns['inuse'][protocol].has_key(host):
                    self.conns['inuse'][protocol][host] = []
            
                if (self.getNumConnsByHost(protocol,host) == 
                                                 self.maxConnsPerServer):
                    self.removeOldestFreeByHost(protocol, host)

                if len(self) == self.maxConns:
                    self.removeOldestFreeConnection()
                if (len(self) < self.maxConns and 
                self.getNumConnsByHost(protocol,host) < self.maxConnsPerServer):
                    if not self.conns['inuse'][protocol].has_key(host):
                        self.conns['inuse'][protocol][host] = []
                    self.conns['inuse'][protocol][host].append(conn)
                    #print "...saving connection"
                #else:
                    #print "...not saving connection"
            finally:
                self.lock.release()

        #print "Making request..."
        try:
            conn.request(method,url,*args,**keywords)
        except socket.error:
            if madeNewConn:
                return None
            else: # We had a connection before. Maybe the connection
                  # just timed out...
                #print "An old connection may have timed out. Trying again."
                self.removeConn(conn)
                return self.getRequest(protocol,host,method,url,*args,**keywords)

        #print "Getting response..."
        try:
            response = conn.getresponse()
        except (HTTPException, socket.timeout):
            if madeNewConn:
                return None
            else: # We had a connection before. Maybe the connection
                  # just timed out...
                #print "An old connection may have timed out. Trying again."
                self.removeConn(conn)
                return self.getRequest(protocol,host,method,url,*args,**keywords)
        #print "Leaving connectionPool"
        return PooledHTTPResponse(conn,response,self)

connectionPool = HTTPConnectionPool()
