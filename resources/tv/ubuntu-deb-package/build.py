#!/usr/bin/env python

import os, sys, urllib
from glob import glob
import shutil

def call(cmd):
    """Call an external command.  If the command doesn't exit with status 0,
    or if it outputs to stderr, an exception will be raised.  Returns stdout.
    """
    rv = os.system(cmd)
    if rv != 0:
        raise OSError("call with %s has return code %s" % (cmd, rv))

def usage():
    sys.stderr.write("""\
Usage: build.py [version] [distribution-name]

For example:
    build.py 0.9.5 feisty
""")
    sys.exit(1)

if len(sys.argv) != 3:
    usage()

version = sys.argv[1]
distro = sys.argv[2]
debian_dir = os.path.normpath(os.path.join(__file__, '..', 'debian-%s' % distro))
tarball_name = 'Democracy-%s.tar.gz' % version
tarball_url = ('ftp://ftp.osuosl.org/pub/pculture.org/democracy/src/' +
        tarball_name)
user = os.environ['USER']

if not os.path.isdir(debian_dir):
    usage()

print """\
Version: %s
Distribution: %s
Debian directory: %s
Tarball URL: %s

Press enter to continue, Ctrl-C to cancel.
""" % (version, distro, debian_dir, tarball_url)
raw_input()
debian_dir = os.path.abspath(debian_dir)

if os.path.exists('build-tmp'):
    shutil.rmtree('build-tmp')
os.mkdir('build-tmp')
os.chdir('build-tmp')

print "downloading tarball"
call('wget %s' % tarball_url)
print "extracting files"
call('tar zxvf %s' %  tarball_name)
os.rename('Democracy-%s' % version, 'democracyplayer-%s' % version)
shutil.copytree(debian_dir, 'democracyplayer-%s/debian' % version)
os.chdir('democracyplayer-%s' % version)
print "building debs"
call('dpkg-buildpackage -us -uc -rfakeroot')
os.chdir('../..')

if os.path.exists(distro):
    shutil.rmtree(distro)
os.mkdir(distro)
call('mv build-tmp/*.deb %s' % distro)
call('apt-ftparchive packages %s > %s/Packages' % (distro, distro))
call('gzip %s/Packages' % distro)
print 'done'
