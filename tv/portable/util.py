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
# the console/log, but not presented in the dialog box.
def failed(when, withExn = False, details = None):
    log = ""
    try:
        import config # probably works at runtime only
        log += "App:        %s\n" % config.get(config.LONG_APP_NAME)
        log += "Publisher:  %s\n" % config.get(config.PUBLISHER)
        log += "Version:    %s\n" % config.get(config.APP_VERSION)
        log += "Revision:   %s\n" % config.get(config.APP_REVISION)
        log += "Update key: %s\n" % config.get(config.UPDATE_KEY)
    except:
        pass
    log += "Time:       %s\n" % time.asctime()
    log += "When:       %s\n" % when
    log += "\n"

    if withExn:
        print "DTV: Failed %s; exception follows." % (when, )
        if details:
            print "DTV: Details: %s" % (details, )
        traceback.print_exc()
        log += "Exception\n---------\n"
        log += traceback.format_exc()
        log += "\n"
    else:
        print "DTV: Failed %s; call stack follows." % (when, )
        if details:
            print "DTV: Details: %s" % (details, )
        traceback.print_stack()
        log += "Call stack\n----------\n"
        log += ''.join(traceback.format_stack())
        log += "\n"
        
    log += "Threads\n-------\n"
    log += "Current: %s\n" % threading.currentThread().getName()
    log += "Active:\n"
    for t in threading.enumerate():
        log += " - %s%s\n" % \
            (t.getName(),
             t.isDaemon() and ' [Daemon]' or '')

    print "----- GENERATING CRASH REPORT -----"
    print log
    print "----- END OF CRASH REPORT -----"

    # Add decorations for Trac
    log = "{{{\n%s}}}\n" % log

    try:
        import app
        app.Controller.instance.getBackendDelegate(). \
            notifyUnkownErrorOccurence(when, log = log)
    except:
        pass
