from dl_daemon import command
import os
import cPickle
import socket
import traceback
from threading import Lock, Thread, Event
from time import sleep
import tempfile

def launchDownloadDaemon(oldpid, port):
    import app
    delegate = app.Controller.instance.getBackendDelegate()
    delegate.launchDownloadDaemon(oldpid, port)
    
def getDataFile():
    try:
        uid = os.getuid()
    except:
        # This works for win32, where we don't have getuid()
        uid = os.environ['USERNAME']
        
    return os.path.join(tempfile.gettempdir(), 'Democracy_Download_Daemon_%s.txt' % uid)

pidfile = None
def writePid(pid):
    """Write out our pid.

    This method locks the pid file until the downloader exits.  On windows
    this is achieved by keeping the file open.  On Unix/OS X, we use the
    fcntl.lockf() function.
    """

    global pidfile
    # NOTE: we want to open the file in a mode the standard open() doesn't
    # support.  We want to create the file if nessecary, but not truncate it
    # if it's already around.  We can't truncate it because on unix we haven't
    # locked the file yet.
    fd = os.open(getDataFile(), os.O_WRONLY | os.O_CREAT)
    pidfile = os.fdopen(fd, 'w')
    try:
        import fcntl
    except:
        pass
    else:
        fcntl.lockf(pidfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pidfile.write("%s\n" % pid)
    pidfile.flush()
    # NOTE: There may be extra data after the line we write left around from
    # prevous writes to the pid file.  This is fine since readPid() only reads
    # the 1st line.
    #
    # NOTE 2: we purposely don't close the file, to achieve locking on
    # windows.

def readPid():
    try:
        f = open(getDataFile(), "r")
    except IOError:
        return None
    try:
        try:
            return int(f.readline())
        except ValueError:
            return None
    finally:
        f.close()

lastDaemon = None

class Daemon:
    def __init__(self):
        global lastDaemon
        lastDaemon = self
        self.shutdown = False
        self.waitingCommands = {}
        self.returnValues = {}
        self.sendLock = Lock() # For serializing data sent over the network
        self.globalLock = Lock() # For serializing access to global object data
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(None)
    
    def listenLoop(self):
        while True:
            #print "Top of dl daemon listen loop"
            comm = cPickle.load(self.stream)
            #print "dl daemon got object %s %s" % (str(comm), comm.id)
            # Process commands in their own thread so actions that
            # need to send stuff over the wire don't hang
            # FIXME: We shouldn't spawn a thread for every command!
            t = Thread(target=lambda:self.processCommand(comm),
                    name="command processor")
            t.setDaemon(False)
            t.start()
            #FIXME This is a bit of a hack
            if isinstance(comm, command.ShutDownCommand):
                # wait for the command thread to send our reply along the
                # socket before quitting
                t.join()
                break

    def processCommand(self, comm):
        if comm.orig:
            comm.setDaemon(self)
            comm.setReturnValue(comm.action())
            comm.send(block=False)
        else:
            self.processReturnValue(comm)

    def processReturnValue(self, comm):
        self.globalLock.acquire()
        try:
            if self.waitingCommands.has_key(comm.id):
                event = self.waitingCommands[comm.id]
                del self.waitingCommands[comm.id]
                self.returnValues[comm.id] = comm.getReturnValue()
            else:
                return
        finally:
            self.globalLock.release()
        event.set()

    def waitForReturn(self, comm):
        self.globalLock.acquire()
        try:
            if self.waitingCommands.has_key(comm.id):
                event = self.waitingCommands[comm.id]
            elif self.returnValues.has_key(comm.id):
                ret = self.returnValues[comm.id]
                del self.returnValues[comm.id]
                return ret
        finally:
            self.globalLock.release()
        event.wait()
        self.globalLock.acquire()
        try:
            ret = self.returnValues[comm.id]
            del self.returnValues[comm.id]
            return ret
        finally:
            self.globalLock.release()
            
    def addToWaitingList(self, comm):
        self.globalLock.acquire()
        try:
            self.waitingCommands[comm.id] = Event()
        finally:
            self.globalLock.release()

    def send(self, comm, block):
        if block:
            self.addToWaitingList(comm)
        raw = cPickle.dumps(comm, cPickle.HIGHEST_PROTOCOL)
        self.sendLock.acquire()
        try:
            cPickle.dump(comm, self.stream, cPickle.HIGHEST_PROTOCOL)
            self.stream.flush() # If I trusted Python sockets to be
                                # properly multithreaded, I'd put this
                                # below the finally block. I don't.
        finally:
            self.sendLock.release()
        if block:
            return self.waitForReturn(comm)


class DownloaderDaemon(Daemon):
    def __init__(self, port):
        # before anything else, write out our PID 
        writePid(os.getpid())
        # connect to the controller and start our listen loop
        Daemon.__init__(self)
        self.socket.connect(('127.0.0.1', port))
        self.stream = self.socket.makefile("r+b")
        print "Downloader Daemon: Connected on port %s" % port
        t = Thread(target = self.downloaderLoop, name = "Downloader Loop")
        t.start()

    def downloaderLoop(self):
        try:
            self.listenLoop()
            print "Downloader listen loop completed"
        finally:
            from dl_daemon import download
            download.shutDown()
            self.shutDown = True

class ControllerDaemon(Daemon):
    def __init__(self):
        Daemon.__init__(self)
        # open a port and start our listen loop
        self.socket.bind( ('127.0.0.1', 0) )
        (myAddr, myPort) = self.socket.getsockname()
        print "Controller Daemon: Listening on %s %s" % (myAddr, myPort)
        self.port = myPort
        self.socket.listen(63)
        self.ready = Event()
        t = Thread(target = self.clientLoop, name = "Controller Loop")
        t.start()
        self.ready.wait()

    def send(self, comm, block):
        # Don't let traffic through until tho downloader child process is
        # ready
        if comm.orig and not self.ready.isSet():
            print 'DTV: Delaying send of %s %s' % (str(comm), comm.id)
            if block:
                self.ready.wait()
            else:
                raise socket.error("server not ready")
        return Daemon.send(self, comm, block)

    def clientLoop(self):
        try:
            while True:
                self.connectToDownloader()
                try:
                    self.listenLoop()
                    print "Controller listen loop completed"
                    break
                except socket.error:
                    # On socket errors, the downloader dies, but the
                    # controller stays alive and restarts the downloader
                    self.ready.clear()
                    print "Socket exception in the controller daemon"
                    traceback.print_exc()
        finally:
            self.shutDown = True

    def connectToDownloader(self):
        # launch a new daemon
        launchDownloadDaemon(readPid(), self.port)
        # wait for the daemon to connect to our port
        (conn, address) = self.socket.accept()
        conn.settimeout(None)
        self.stream = conn.makefile("r+b")
