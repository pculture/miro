import re
import subprocess
import string
import os
import urllib
import threading
import traceback
import time
import sys

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = x.replace("\\", "\\\\") # \       -> \\
    x = x.replace("\"", "\\\"") # "       -> \"  
    x = x.replace("'",  "\\'")  # '       -> \'
    x = x.replace("\n", "\\n")  # newline -> \n
    x = x.replace("\r", "\\r")  # CR      -> \r
    return x

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
        p1 = subprocess.Popen(["svn", "info", file], stdout=subprocess.PIPE) 
        p2 = subprocess.Popen(["grep", "Revision:"], \
                              stdin=p1.stdout, stdout=subprocess.PIPE) 
        output = re.search('Revision: (.*)', p2.communicate()[0])
        if not output:
            return None
        else:
            return int(output.group(1))
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
        header += "App:        %s\n" % config.get(config.LONG_APP_NAME)
        header += "Publisher:  %s\n" % config.get(config.PUBLISHER)
        header += "Platform:   %s\n" % config.get(config.APP_PLATFORM)
        header += "Version:    %s\n" % config.get(config.APP_VERSION)
        header += "Serial:     %s\n" % config.get(config.APP_SERIAL)
        header += "Revision:   %s\n" % config.get(config.APP_REVISION)
    except:
        pass
    header += "Time:       %s\n" % time.asctime()
    header += "When:       %s\n" % when
    header += "\n"

    if withExn:
        header += "Exception\n---------\n"
        if details:
            header += "Details: %s" % (details, )
        header += traceback.format_exc()
        header += "\n"
    else:
        header += "Call stack\n----------\n"
        if details:
            header += "Details: %s" % (details, )
        header += ''.join(traceback.format_stack())
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
    logFile = config.get(config.LOG_PATHNAME)
    if logFile is None:
        logContents = "No logfile available on this platform.\n"
    else:
        try:
            f = open(logFile, "rt")
            logContents = "Log\n---\n"
            logContents += f.read()
            f.close()
        except:
            logContents = "Couldn't read logfile '%s':\n" % (logFile, )
            logContents += traceback.format_exc()
    report += "{{{\n%s}}}\n" % logContents

    # Dump the header for the report we just generated to the log, in
    # case there are multiple failures or the user sends in the log
    # instead of the report from the dialog box. (Note that we don't
    # do this until we've already read the log into the dialog
    # message.)
    print "----- CRASH REPORT (DANGER CAN HAPPEN) -----"
    print header
    print "----- END OF CRASH REPORT -----"

    try:
        import app
        app.Controller.instance.getBackendDelegate(). \
            notifyUnkownErrorOccurence(when, log = report)
    except:
        pass



            
