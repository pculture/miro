from dl_daemon import command
import os
import cPickle
import socket
import traceback
from threading import Lock, Thread, Event
from time import sleep

def getDataFile():
    return os.path.join(os.environ['TMP'], 'Democracy_Download_Daemon.txt')

lastDaemon = None

class Daemon:
    def __init__(self, server = False):
        global lastDaemon
        lastDaemon = self
        self.server = server
        self.waitingCommands = {}
        self.returnValues = {}
        self.sendLock = Lock() # For serializing data sent over the network
        self.globalLock = Lock() # For serializing access to global object data
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(None)
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
            t = Thread(target = self.clientLoop, name = "Client Loop")
            t.start()

    def clientLoop(self):
        while True:
            connected = False
            port = -1
            while not connected: #FIXME: add code to spawn server
                try:
                    if (port > 0):
                        print "Client Connecting to %d" % port
                        self.socket.connect( ('127.0.0.1',port))
                        connected = True
                except:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(None)
                    sleep(5)
                if not connected:
                    try:
                        f = open(getDataFile(),"rb")
                        port = int(f.readline())
                        pid = int(f.readline())
                        f.close()
                    except:
                        pass
            self.stream = self.socket.makefile("r+b")
            self.listenLoop()

    def serverLoop(self):
        while True:
            print "server listening..."
            (conn, address) = self.socket.accept()
            conn.settimeout(None)
            self.stream = conn.makefile("r+b")
            self.listenLoop()

    def listenLoop(self):
        try:
            cont = True
            while cont:
                print "Top of dl daemon listen loop"
                comm = cPickle.load(self.stream)
                print "dl daemon got object %s %s" % (str(comm), comm.id)
                # Process commands in their own thread so actions that
                # need to send stuff over the wire don't hang
                t = Thread(target=lambda:self.processCommand(comm), name="command processor")
                t.setDaemon(False)
                t.start()
        except:
            traceback.print_exc()

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
