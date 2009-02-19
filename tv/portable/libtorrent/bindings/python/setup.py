#!/usr/bin/env python

from distutils.core import setup, Extension
import os
import platform
import sys

if 'boost_python-mt-1_35' == '':
	print 'You need to pass --enable-python-binding to configure in order ',
	print 'to properly use this setup. There is no boost.python library configured now'
	sys.exit(1)

def parse_cmd(cmdline, prefix, keep_prefix = False):
	ret = []
	for token in cmdline.split():
		if token[:len(prefix)] == prefix:
			if keep_prefix:
				ret.append(token)
			else:
				ret.append(token[len(prefix):])
	return ret

def arch():
	if platform.system() != 'Darwin': return []
	a = os.uname()[4]
	if a == 'Power Macintosh': a = 'ppc'
	return ['-arch', a]

if platform.system() == 'Windows':
# on windows, build using bjam and build an installer
	import shutil
	if os.system('bjam boost=source link=static boost-link=static release msvc-7.1 optimization=space') != 0:
		print 'build failed'
		sys.exit(1)
	try: os.mkdir(r'build')
	except: pass
	try: os.mkdir(r'build\lib')
	except: pass
	try: os.mkdir(r'libtorrent')
	except: pass
	shutil.copyfile(r'bin\msvc-7.1\release\boost-source\link-static\optimization-space\threading-multi\libtorrent.pyd', r'.\build\lib\libtorrent.pyd')
	setup( name='python-libtorrent',
		version='0.14.2',
		author = 'Arvid Norberg',
		author_email='arvid@rasterbar.com',
		description = 'Python bindings for libtorrent-rasterbar',
		long_description = 'Python bindings for libtorrent-rasterbar',
		url = 'http://www.rasterbar.com/products/libtorrent/index.html',
		platforms = 'Windows',
		license = 'Boost Software License - Version 1.0 - August 17th, 2003',
		packages = ['libtorrent'],
	)
	sys.exit(0)

source_list = os.listdir(os.path.join(os.path.dirname(__file__), "src"))
source_list = [os.path.join("src", s) for s in source_list if s.endswith(".cpp")]

extra_cmd = '-DTORRENT_USE_OPENSSL -DTORRENT_LINKING_SHARED   -D_THREAD_SAFE  -pthread -I/opt/local/include   -lboost_filesystem-mt-1_35 -lboost_thread-mt-1_35    -lssl -lcrypto -lboost_system-mt-1_35 -L/opt/local/lib -L/opt/local/lib -L/usr/lib -I/opt/local/include/boost-1_35 -I/usr/include/python2.5 -I/usr/include/openssl -DHAVE_SSL'

setup( name='python-libtorrent',
	version='0.14.2',
	author = 'Arvid Norberg',
	author_email='arvid@rasterbar.com',
	description = 'Python bindings for libtorrent-rasterbar',
	long_description = 'Python bindings for libtorrent-rasterbar',
	url = 'http://www.rasterbar.com/products/libtorrent/index.html',
	platforms = 'any',
	license = 'Boost Software License - Version 1.0 - August 17th, 2003',
	ext_modules = [Extension('libtorrent',
		sources = source_list,
		language='c++',
		include_dirs = ['../../include','../../include/libtorrent'] + parse_cmd(extra_cmd, '-I'),
		library_dirs = ['../../src/.libs'] + parse_cmd(extra_cmd, '-L'),
		extra_link_args = '-L/opt/local/lib -L/opt/local/lib'.split() + arch(),
		extra_compile_args = parse_cmd(extra_cmd, '-D', True) + arch(),
		libraries = ['torrent-rasterbar','boost_python-mt-1_35'] + parse_cmd(extra_cmd, '-l'))],
)
