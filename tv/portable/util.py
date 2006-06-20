import re
import subprocess
import string
import os
import prefs
import urllib
import socket
import threading
import traceback
import time
import sys
from BitTornado.clock import clock

inDownloader = False
# this gets set to True when we're in the download process.

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = x.replace("\\", "\\\\") # \       -> \\
    x = x.replace("\"", "\\\"") # "       -> \"  
    x = x.replace("'",  "\\'")  # '       -> \'
    x = x.replace("\n", "\\n")  # newline -> \n
    x = x.replace("\r", "\\r")  # CR      -> \r
    return x

def getNiceStack():
    """Get a stack trace that's a easier to read that the full one.  """
    stack = traceback.extract_stack()
    # We don't care about the unit test lines
    while (len(stack) > 0 and
        os.path.basename(stack[0][0]) == 'unittest.py' or 
        (isinstance(stack[0][3], str) and 
            stack[0][3].startswith('unittest.main'))):
        stack = stack[1:]
    # remove after the call to util.failed
    for i in xrange(len(stack)):
        if (os.path.basename(stack[i][0]) == 'util.py' and 
                stack[i][2] in ('failed', 'failedExn')):
            stack = stack[:i+1]
            break
    # remove trapCall calls
    stack = [i for i in stack if i[2] != 'trapCall']
    return stack

# Parse a configuration file in a very simple format. Each line is
# either whitespace or "Key = Value". Whitespace is ignored at the
# beginning of Value, but the remainder of the line is taken
# literally, including any whitespace. There is no way to put a
# newline in a value. Returns the result as a dict.
def readSimpleConfigFile(path):
    ret = {}

    f = open(path, "rt")
    for line in f.readlines():
        # Skip blank lines
        if re.match("^[ \t]*$", line):
            continue

        # Otherwise it'd better be a configuration setting
        match = re.match(r"^([^ ]+) *= *([^\r\n]*)[\r\n]*$", line)
        if not match:
            print "WARNING: %s: ignored bad configuration directive '%s'" % \
                (path, line)
            continue
        
        key = match.group(1)
        value = match.group(2)
        if key in ret:
            print "WARNING: %s: ignored duplicate directive '%s'" % \
                (path, line)
            continue

        ret[key] = value

    return ret

# Given a dict, write a configuration file in the format that
# readSimpleConfigFile reads.
def writeSimpleConfigFile(path, data):
    f = open(path, "wt")

    for (k, v) in data.iteritems():
        f.write("%s = %s\n" % (k, v))
    
    f.close()

# Called at build-time to ask Subversion for the revision number of
# this checkout. Going to fail without Cygwin. Yeah, oh well. Pass the
# file or directory you want to use as a reference point. Returns an
# integer on success or None on failure.
def queryRevision(file):
    try:
        p = subprocess.Popen(["svn", "info", file], stdout=subprocess.PIPE) 
        info = p.stdout.read()
        p.stdout.close()
        url = re.search("URL: (.*)", info).group(1)
        revision = re.search("Revision: (.*)", info).group(1)
        return (url, revision)
    except:
        # whatever
        return None

# 'path' is a path that could be passed to open() to open a file on
# this platform. It must be an absolute path. Return the file:// URL
# that would refer to the same file.
def absolutePathToFileURL(path):
    parts = string.split(path, os.sep)
    parts = [urllib.quote(x, ':') for x in parts]
    if len(parts) > 0 and parts[0] == '':
        # Don't let "/foo/bar" become "file:////foo/bar", but leave
        # "c:/foo/bar" becoming "file://c:/foo/bar" -- technically :
        # should become | (but only in a drive name?) but most
        # consumers will let us get by with that.
        parts = parts[1:]
    return "file:///" + '/'.join(parts)


# Shortcut for 'failed' with the exception flag.
def failedExn(when, **kwargs):
    failed(when, withExn = True, **kwargs)

# Puts up a dialog with debugging information encouraging the user to
# file a ticket. (Also print a call trace to stderr or whatever, which
# hopefully will end up on the console or in a log.) 'when' should be
# something like "when trying to play a video." The user will see
# it. If 'withExn' is true, last-exception information will be printed
# to. If 'detail' is true, it will be included in the report and the
# the console/log, but not presented in the dialog box flavor text.
def failed(when, withExn = False, details = None):
    print "failed() called; generating crash report."

    header = ""
    try:
        import config # probably works at runtime only
        header += "App:        %s\n" % config.get(prefs.LONG_APP_NAME)
        header += "Publisher:  %s\n" % config.get(prefs.PUBLISHER)
        header += "Platform:   %s\n" % config.get(prefs.APP_PLATFORM)
        header += "Version:    %s\n" % config.get(prefs.APP_VERSION)
        header += "Serial:     %s\n" % config.get(prefs.APP_SERIAL)
        header += "Revision:   %s\n" % config.get(prefs.APP_REVISION)
    except:
        pass
    header += "Time:       %s\n" % time.asctime()
    header += "When:       %s\n" % when
    header += "\n"

    if withExn:
        header += "Exception\n---------\n"
        header += ''.join(traceback.format_exception(*sys.exc_info()))
        header += "\n"
    if details:
        header += "Details: %s\n" % (details, )
    header += "Call stack\n----------\n"
    try:
        stack = getNiceStack()
    except:
        stack = traceback.extract_stack()
    header += ''.join(traceback.format_list(stack))
    header += "\n"

    header += "Threads\n-------\n"
    header += "Current: %s\n" % threading.currentThread().getName()
    header += "Active:\n"
    for t in threading.enumerate():
        header += " - %s%s\n" % \
            (t.getName(),
             t.isDaemon() and ' [Daemon]' or '')

    # Combine the header with the logfile contents, if available, to
    # make the dialog box crash message. {{{ and }}} are Trac
    # Wiki-formatting markers that force a fixed-width font when the
    # report is pasted into a ticket.
    report = "{{{\n%s}}}\n" % header

    def readLog(logFile, logName="Log"):
        try:
            f = open(logFile, "rt")
            logContents = "%s\n---\n" % logName
            logContents += f.read()
            f.close()
        except:
            logContents = None
        return logContents

    logFile = config.get(prefs.LOG_PATHNAME)
    downloaderLogFile = config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    if logFile is None:
        logContents = "No logfile available on this platform.\n"
    else:
        logContents = readLog(logFile)
    if downloaderLogFile is not None:
        if logContents is not None:
            logContents += "\n" + readLog(downloaderLogFile, "Downloader Log")
        else:
            logContents = readLog(downloaderLogFile)

    if logContents is not None:
        report += "{{{\n%s}}}\n" % logContents

    # Dump the header for the report we just generated to the log, in
    # case there are multiple failures or the user sends in the log
    # instead of the report from the dialog box. (Note that we don't
    # do this until we've already read the log into the dialog
    # message.)
    print "----- CRASH REPORT (DANGER CAN HAPPEN) -----"
    print header
    print "----- END OF CRASH REPORT -----"

    if not inDownloader:
        try:
            import app
            app.delegate. \
                notifyUnkownErrorOccurence(when, log = report)
        except Exception, e:
            print "Execption when reporting errror.."
            traceback.print_exc()
    else:
        from dl_daemon import command, daemon
        c = command.DownloaderErrorCommand(daemon.lastDaemon, report)
        c.send(block=False)

class AutoflushingStream:
    """Converts a stream to an auto-flushing one.  It behaves in exactly the
    same way, except all write() calls are automatically followed by a
    flush().
    """
    def __init__(self, stream):
        self.__dict__['stream'] = stream
    def write(self, *args):
        self.stream.write(*args)
        self.stream.flush()
    def __getattr__(self, name):
        return self.stream.__getattr__(name)
    def __setattr__(self, name, value):
        return self.stream.__setattr__(name, value)

def makeDummySocketPair():
    """Create a pair of sockets connected to each other on the local
    interface.  Used to implement SocketHandler.wakeup().
    """

    dummy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_server.bind( ('127.0.0.1', 0) )
    dummy_server.listen(1)
    server_address = dummy_server.getsockname()
    first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    first.connect(server_address)
    second, address = dummy_server.accept()
    dummy_server.close()
    return first, second

def trapCall(when, function, *args, **kwargs):
    """Make a call to a function, but trap any exceptions and do a failedExn
    call for them.  Return True if the function successfully completed, False
    if it threw an exception
    """

    try:
        function(*args, **kwargs)
        return True
    except:
        failedExn(when)
        return False

cumulative = {}
cancel = False

def timeTrapCall(when, function, *args, **kwargs):
    global cancel
    cancel = False
    start = clock()
    retval = trapCall (when, function, *args, **kwargs)
    end = clock()
    if cancel:
        return retval
    if end-start > 0.5:
        print "WARNING: %s too slow (%.3f secs)" % (
            when, end-start)
    try:
        total = cumulative[when]
    except:
        total = 0
    total += end - start
    cumulative[when] = total
    if total > 5.0:
        print "WARNING: %s cumulative is too slow (%.3f secs)" % (
            when, total)
        cumulative[when] = 0
    cancel = True
    return retval

        
