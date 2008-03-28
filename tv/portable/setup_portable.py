
# Copyright (c) 2006 Zach Tibbitts ('zachtib') <zach@collegegeek.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, write to:
#     The Free Software Foundation, Inc.,
#     51 Franklin Street, Fifth Floor
#     Boston, MA  02110-1301, USA.
#
#  In addition, as a special exception, the copyright holders give
#  permission to link the code of portions of this program with the OpenSSL
#  library.
#  You must obey the GNU General Public License in all respects for all of
#  the code used other than OpenSSL. If you modify file(s) with this
#  exception, you may extend this exception to your version of the file(s),
#  but you are not obligated to do so. If you do not wish to do so, delete
#  this exception statement from your version. If you delete this exception
#  statement from all source files in the program, then also delete it here.

import os
from miro import platform
print "Attempting to detect your system information"
if platform.machine() == "i386" or platform.machine() == "i686":
    print "32bit x86 system detected"
    ARCH = "x86"
elif platform.machine() == "x86_64" or platform.machine() == "amd64":
    print "64bit x86_64 system detected"
    ARCH = "x64"
elif platform.machine() == "ppc":
    print "PowerPC system detected"
    ARCH = "ppc"
else:
    print "Couldn't detect CPU architecture"
    ARCH = ""
if platform.system() == "Linux":
    print "Linux operating system detected"
    OS = "linux"
elif platform.system() == "Darwin" :
    print "Darwin / OS X system detected"
    OS = "osx"
elif platform.system() == "FreeBSD" :
    print "FreeBSD operating system detected"
    OS = "freebsd"
elif platform.system() in ('Windows', 'Microsoft'): 
    print "Windows system detected"
    OS = "win"
elif os.name == "posix":
    print "Unix system detected"
    OS = "nix"
else:
    print "Couldn't detect operating system"
    OS = ""

#import os.path, glob
from distutils.core import Extension
from distutils import sysconfig
#import shutil
#from distutils import cmd
#from distutils.command.install import install as _install
#from distutils.command.install_data import install_data as _install_data
#from distutils.command.build import build as _build
#if OS == "win":
#    from distutils.command.build_ext import build_ext as _build_ext
#import msgfmt
#
python_version = platform.python_version()[0:3]


# NOTE: The following "hack" removes the -g and -Wstrict-prototypes
# build options from the command that will compile the C++ module,
# deluge_core.  While we understand that you aren't generally
# encouraged to do this, we have done so for the following reasons:
# 1) The -g compiler option produces debugging information about
#    the compiled module.  However, this option increases the 
#    size of deluge_core.so from ~1.9MB to 13.6MB and slows down
#    the program's execution without offering any benefits 
#    whatsoever.
# 2) -Wstrict-prototypes is not a valid C++ build option, and the
#    compiler will throw a number of warnings at compile time.
#    While this does not really impact anything, it makes it
#    seem as if something is going wrong with the compile, and
#    it has been removed to prevent confusion.

def libtorrent_extension(portable_dir):
    include_dirs = [os.path.join(portable_dir, x) for x in
                            ['libtorrent/include', 'libtorrent/include/libtorrent']]
    
    if not OS == "win":
        EXTRA_COMPILE_ARGS = ["-Wno-missing-braces", 
                    "-DHAVE_INCLUDE_LIBTORRENT_ASIO____ASIO_HPP=1", 
                    "-DHAVE_INCLUDE_LIBTORRENT_ASIO_SSL_STREAM_HPP=1", 
                    "-DHAVE_INCLUDE_LIBTORRENT_ASIO_IP_TCP_HPP=1", 
                    "-DHAVE_PTHREAD=1", "-DTORRENT_USE_OPENSSL=1", "-DHAVE_SSL=1", 
                    "-DNDEBUG=1", "-O2"]
        if ARCH == "x64":
            EXTRA_COMPILE_ARGS.append("-DAMD64")
    
        if OS == "linux":
            if os.WEXITSTATUS(os.system('grep -iq "Debian GNU/Linux 4.0\|Ubuntu 7.04\|Ubuntu 6.06\|Ubuntu 6.10\|Fedora Core release 6\|openSUSE 10.2\|openSUSE 10.3\|Mandriva Linux release 2007.1\|Fedora release 7\|BLAG release 60001\|Yellow Dog Linux release 5.0 (Phoenix)\|CentOS release 5 (Final)" /etc/issue')) == 0:
                boosttype = 'nomt'
            else:
                boosttype = 'mt'
        elif OS == "freebsd":
            boosttype = 'nomt'
        else:
            boosttype = 'mt'
        
        removals = ['-Wstrict-prototypes']
    
        if python_version == '2.5':
            cv_opt = sysconfig.get_config_vars()["CFLAGS"]
            for removal in removals:
                cv_opt = cv_opt.replace(removal, " ")
            sysconfig.get_config_vars()["CFLAGS"] = ' '.join(cv_opt.split())
        else:
            cv_opt = sysconfig.get_config_vars()["OPT"]
            for removal in removals:
                cv_opt = cv_opt.replace(removal, " ")
            sysconfig.get_config_vars()["OPT"] = ' '.join(cv_opt.split())
    else:
        boosttype = 'mt'
        EXTRA_COMPILE_ARGS = [  '-DBOOST_WINDOWS',
                                '-DWIN32_LEAN_AND_MEAN',
                                '-D_WIN32_WINNT=0x0500',
                                '-D__USE_W32_SOCKETS',
                                '-D_WIN32',
                                '-DWIN32',
                                '-DBOOST_ALL_NO_LIB',
                                '-D_FILE_OFFSET_BITS=64',
                                '-DBOOST_THREAD_USE_LIB',
                                '-DTORRENT_USE_OPENSSL=1',
                                '-DNDEBUG=1',
                                '/EHa', '/GR',
                                ]
                                 
    # NOTE: The Rasterbar Libtorrent source code is in the libtorrent/ directory
    # inside of Deluge's source tarball.  On several occasions, it has been 
    # pointed out to us that we should build against the system's installed 
    # libtorrent rather than our internal copy, and a few people even submitted
    # patches to do just that. However, as of now, this version
    # of libtorrent is not available in Debian, and as a result, Ubuntu. Once
    # libtorrent-rasterbar is available in the repositories of these distributions,
    # we will probably begin to build against a system libtorrent, but at the
    # moment, we are including the source code to make packaging on Debian and
    # Ubuntu possible.
    if not OS == "win":
        if boosttype == "nomt":
            librariestype = ['boost_python', 'boost_filesystem', 'boost_date_time',
                'boost_thread', 'z', 'pthread', 'ssl']
            print 'Libraries nomt' 
        elif boosttype == "mt":
            librariestype = ['boost_python', 'boost_filesystem-mt', 'boost_date_time-mt',
                'boost_thread-mt', 'z', 'pthread', 'ssl']
            print 'Libraries mt'
    else:
            librariestype = ['boost_python', 'boost_filesystem-mt', 'boost_date_time-mt',
                'boost_thread-mt', 'z', 'ssl' ,'wsock32' ,'crypto' ,'gdi32'
                ,'ws2_32' 'zlib']
            print 'Libraries mt'
    
    #### The libtorrent extension ####
    def fetchCpp():
        for root,dirs,files in os.walk(os.path.join(portable_dir, 'libtorrent')):
            if '.svn' in dirs:
                dirs.remove('.svn')
            for file in files:
                if file.endswith('.cpp'):
                    yield os.path.join(root,file)
    
    sources=list(fetchCpp())
    if not OS == "win":
        sources.remove(os.path.join(portable_dir, 'libtorrent/src/file_win.cpp'))
        return Extension("miro.libtorrent", 
                         include_dirs = include_dirs,
                         libraries = librariestype,
                         extra_compile_args = EXTRA_COMPILE_ARGS,
                         sources = sources)
    else:
        sources.remove(os.path.join(portable_dir, 'libtorrent\\src\\file.cpp'))
        return Extension("miro.libtorrent", 
                         include_dirs = include_dirs,
                         libraries = librariestype,
                         extra_compile_args = EXTRA_COMPILE_ARGS,
                         sources = sources)
