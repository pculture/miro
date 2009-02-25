#!/usr/bin/env python

# FIXME - at some point this should remove the .svn stuff from the 
# debian-x directory.  perhaps we should be doing a checkout and use
# the stuff there?  wbg 10-23-2007

import os, sys, urllib, os.path
from glob import glob
import shutil

SYNTAX = """
Usage: build.py [version] [distribution-name] [source tarball path/url]

Examples:

    build.py 0.9.5 feisty http://example.com/Miro-0.9.5.tar.gz
    build.py 0.9.9.9-rc0 gutsy http://example.com/Miro-0.9.9.9-rc0.tar.gz

    build.py 0.9.5 feisty ./Miro-0.9.5.tar.gz
"""

PBUILDERHOME = os.path.join(os.path.expanduser("~"), ".pbuilder")
 
def call(cmd):
    """Call an external command.  If the command doesn't exit with status 0,
    or if it outputs to stderr, an exception will be raised.  Returns stdout.
    """
    rv = os.system(cmd)
    if rv != 0:
        raise OSError("call with %s has return code %s" % (cmd, rv))

def usage():
    sys.stderr.write(SYNTAX)
    sys.exit(1)

if len(sys.argv) < 4:
    usage()

version = sys.argv[1]
distro = sys.argv[2]
debian_dir = os.path.normpath(os.path.join(__file__, '..', 'debian-%s' % distro))
tarball_name = 'Miro-%s.tar.gz' % version
tarball_url = sys.argv[3]
user = os.environ['USER']
pbuilder_tgz = os.path.join(PBUILDERHOME, "%s-base.tgz" % distro)

if not os.path.isdir(debian_dir):
    usage()

print """\
Version:          %s
Distribution:     %s
Debian directory: %s
Tarball Path/URL: %s
PBuilder base:    %s

Press enter to continue, Ctrl-C to cancel.
""" % (version, distro, debian_dir, tarball_url, pbuilder_tgz)
raw_input()
debian_dir = os.path.abspath(debian_dir)

if os.path.exists('build-tmp'):
    shutil.rmtree('build-tmp')
os.mkdir('build-tmp')

if tarball_url.startswith("http"):
    # change directories, then wget the tarball
    print "build.py: downloading tarball"
    os.chdir('build-tmp')
    call('wget %s' % tarball_url)
else:
    # copy the tarball, then switch directories
    print "build.py: copying tarball"
    call('cp %s build-tmp/' % tarball_url)
    os.chdir('build-tmp')


print "build.py: extracting files"
call('tar zxvf %s' %  tarball_name)
call('cp %s %s' % (tarball_name, "miro_%s.orig.tar.gz" % version))
os.rename('Miro-%s' % version, 'miro-%s' % version)
shutil.copytree(debian_dir, 'miro-%s/debian' % version)
os.chdir('miro-%s' % version)
# remove the .svn directories
call('rm -rf debian/.svn')
call('rm -rf debian/patches/.svn')

print "build.py: building source and .dsc file"
call('dpkg-buildpackage -S -us -uc -rfakeroot')

os.chdir('../..')

if os.path.exists(distro):
    shutil.rmtree(distro)
os.mkdir(distro)

call('mv build-tmp/miro_* %s' % distro)

print "build.py: running pbuilder"
call('pbuilder build --basetgz %s --buildresult ./%s %s/*.dsc' % (pbuilder_tgz, distro, distro))

print 'build.py: done'
