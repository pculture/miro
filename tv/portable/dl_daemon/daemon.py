from dl_daemon import command
import os
import cPickle
import socket
import traceback
from threading import Lock, Thread, Event
from time import sleep
import tempfile

def launchDownloadDaemon(oldpid = None):
    import app
    delegate = app.Controller.instance.getBackendDelegate()
    delegate.launchDownloadDaemon(oldpid)
    
def getDataFile():
    try:
        uid = os.getuid()
    except:
        # This works for win32, where we don't have getuid()
        uid = os.environ['USER']
        
    return os.path.join(tempfile.gettempdir(), 'Democracy_Download_Daemon_%s.txt' % uid)

lastDaemon = None

class Daemon:
    def __init__(self, server = False, onShutdown = lambda:None):
        global lastDaemon
        lastDaemon = self
        self.shutdown = False
        self.server = server
        self.waitingCommands = {}
        self.returnValues = {}
        self.sendLock = Lock() # For serializing data sent over the network
        self.globalLock = Lock() # For serializing access to global object data
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(None)
        self.onShutdown = onShutdown
        if server:
            self.socket.bind( ('127.0.0.1', 0) )
            (myAddr, myPort) = self.socket.getsockname()
            print "DownloadServer Daemon: Listening on %s %s" % (myAddr, myPort)
            self.port = myPort
            self.socket.listen(63)
            f = open(getDataFile(),"wb")
            f.write("%s\n%s\n" % (myPort, os.getpid()))
            f.close()
            self.socket.listen(63)
            t = Thread(target = self.serverLoop, name = "Server Loop")
            t.start()
        else:
            # make sure we don't start until the server
            # has asked us for all it's config info
            self.ready = Event()
            t = Thread(target = self.clientLoop, name = "Client Loop")
            t.start()
            self.ready.wait()
    
    def clientConnect(self):
        # There's still a possible race condition in the case where
        # two copies of the daemon start at nearly the same time
        MAX_TRIES = 3
        connected = False
        port = None
        pid = None
        tries = 0
        try:
            f = open(getDataFile(),"rb")
            port = int(f.readline())
            pid = int(f.readline())
            f.close()
        except:
            pass
        try:
            if (port is not None):
                print "dtv: Client Connecting to %d" % port
                self.socket.connect( ('127.0.0.1',port))
                connected = True
        except:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(None)
            launchDownloadDaemon(pid)
            sleep(1)
            
        while not connected:
            tries += 1
            try:
                f = open(getDataFile(),"rb")
                port = int(f.readline())
                pid = int(f.readline())
                f.close()
            except:
                pass
            try:
                if (port is not None):
                    print "dtv: Client Connecting to %d" % port
                    self.socket.connect( ('127.0.0.1',port))
                    connected = True
            except:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(None)
                sleep(1)
            if not connected and tries == MAX_TRIES:
                print "dtv: launching download daemon"
                launchDownloadDaemon(pid)
                sleep(3)
                tries = 0
                        
    def clientLoop(self):
        cont = True
        while cont:
            self.clientConnect()
            self.stream = self.socket.makefile("r+b")
            cont = self.listenLoop()
        self.onShutdown()
        self.shutdown = True

    def serverLoop(self):
        cont = True
        while cont:
            print "server listening..."
            (conn, address) = self.socket.accept()
            conn.settimeout(None)
            self.stream = conn.makefile("r+b")
            cont = self.listenLoop()
        self.onShutdown()
        self.shutdown = True

    def listenLoop(self):
        try:
            cont = True
            while cont:
                #print "Top of dl daemon listen loop"
                comm = cPickle.load(self.stream)
                #print "dl daemon got object %s %s" % (str(comm), comm.id)
                # Process commands in their own thread so actions that
                # need to send stuff over the wire don't hang
                # FIXME: We shouldn't spawn a thread for every command!
                t = Thread(target=lambda:self.processCommand(comm), name="command processor")
                t.setDaemon(False)
                t.start()
                #FIXME This is a bit of a hack
                cont = not isinstance(comm, command.ShutDownCommand)
            print "Leaving daemon listen loop"
            return False # Stop looping
        except:
            traceback.print_exc()
            # On socket errors, the daemon dies, but the client stays
            # alive so it can restart the daemon
            return not self.server

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
        # Don't let client traffic through until the server is ready
        if comm.orig and not self.server and not self.ready.isSet():
            print 'DTV: Delaying send of %s %s' % (str(comm), comm.id)
            if block:
                self.ready.wait()
            else:
                raise socket.error

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
