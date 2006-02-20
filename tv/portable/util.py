import re
import subprocess
import string
import os
import urllib

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
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
