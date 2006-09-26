#!/usr/local/bin/python
## this script copies BitTorrent dependent modules into the resource dir in a 
## configuration independent way (hopefully)
## this script reportedly doesn't deal well with spaces in the path to your project (who_uses_spaces_anyways?)

from os.path import join
from os import makedirs, system, environ, listdir, unlink
from shutil import copy
from compileall import compile_dir
import sys

sys.prefix='/usr/local'
py_path = 'lib/python2.3'
so_path = 'lib/python2.3/lib-dynload'


## add dependend modules to one or the other list, depending on the type
## there are probably some extra modules in here that aren't actually used
py_modules = ['StringIO', 'UserDict', '__future__', 'atexit', 'base64', 'bisect', 'codecs', 'copy', 'copy_reg', 'dis', 'ftplib', 'inspect', 'getopt', 'getpass', 'gopherlib', 'gzip', 'httplib', 'linecache', 'macpath', 'macurl2path', 'mimetools', 'mimetypes', 'ntpath', 'nturl2path', 'opcode', 'os', 'popen2', 'posixpath', 'pprint', 'pre', 'quopri', 'random', 're', 'repr', 'rfc822', 'socket', 'sre', 'sre_compile', 'sre_constants', 'sre_parse', 'stat', 'string', 'StringIO', 'tempfile', 'termios', 'threading', 'traceback', 'types', 'token', 'tokenize', 'urllib', 'urllib2', 'urlparse', 'uu', 'warnings']

so_modules = ['_random', '_socket', 'binascii', 'cStringIO', 'math', 'md5', 'pcre', 'pwd', 'select', 'sha', 'strop', 'struct', 'time', 'zlib']

res = join(environ['SYMROOT'], '%s.%s/Contents/Resources' % (environ['PRODUCT_NAME'], environ['WRAPPER_EXTENSION']))
py = join(res, 'lib/python2.3')
dy = join(py, 'lib-dynload')
bt = join(res, 'BitTorrent')

try:
    makedirs(py)
except OSError, reason:
    # ignore errno=17 directory already exists...
    if reason.errno != 17:
	raise OSError, reason

try:
    makedirs(dy)
except OSError, reason:
    # ignore errno=17 directory already exists...
    if reason.errno != 17:
	raise OSError, reason

try:
    makedirs(bt)
except OSError, reason:
    # ignore errno=17 directory already exists...
    if reason.errno != 17:
	raise OSError, reason

print "Copying depedent Python modules..."

# python lib
source = join(sys.prefix, py_path)
for module in py_modules:
    copy(join(source, module +".py"), py)

# c modules
source = join(sys.prefix, so_path)
for module in so_modules:
    print join(source, module+".so")
    copy(join(source, module +".so"), dy)

# bt modules
source = join(environ['SRCROOT'], '../BitTorrent')
for f in listdir(source):
    if f[-3:] == '.py':
	copy(join(source, f), bt)

#copy btmakemetafile.py
copy(join(environ['SRCROOT'], "../btmakemetafile.py"), res)
#copy btcompletedir.py
copy(join(environ['SRCROOT'], "../btcompletedir.py"), res)


# compile and remove sources
compile_dir(res)
for f in listdir(res):
    if f[-3:] == '.py':
	unlink(join(res, f))
for f in listdir(bt):
    if f[-3:] == '.py':
	unlink(join(bt, f))
for f in listdir(py):
    if f[-3:] == '.py':
	unlink(join(py, f))

# strip c modules
system("strip -x %s" % join(dy, "*.so"))
