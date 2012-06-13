#!/usr/bin/env python

# Miro - an RSS based video player application
# Copyright (C) 2012
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

# test-setup.py -- distutils script to build things for test.py

from distutils.core import setup
from distutils.extension import Extension
import subprocess

def get_command_output(cmd, warnOnStderr=True, warnOnReturnCode=True):
    """Wait for a command and return its output.  Check for common
    errors and raise an exception if one of these occurs.
    """
    p = subprocess.Popen(cmd, shell=True, close_fds=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if warnOnStderr and stderr != '':
        raise RuntimeError("%s outputted the following error:\n%s" %
                           (cmd, stderr))
    if warnOnReturnCode and p.returncode != 0:
        raise RuntimeError("%s had non-zero return code %d" %
                           (cmd, p.returncode))
    return stdout

def parse_pkg_config(command, components, options_dict=None):
    """Helper function to parse compiler/linker arguments from
    pkg-config and update include_dirs, library_dirs, etc.

    We return a dict with the following keys, which match up with
    keyword arguments to the setup function: include_dirs,
    library_dirs, libraries, extra_compile_args.

    Command is the command to run (pkg-config, etc).  Components is a
    string that lists the components to get options for.

    If options_dict is passed in, we add options to it, instead of
    starting from scratch.
    """
    if options_dict is None:
        options_dict = {
            'include_dirs': [],
            'library_dirs': [],
            'libraries': [],
            'extra_compile_args': []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = get_command_output(commandLine).strip()
    for comp in output.split():
        prefix, rest = comp[:2], comp[2:]
        if prefix == '-I':
            options_dict['include_dirs'].append(rest)
        elif prefix == '-L':
            options_dict['library_dirs'].append(rest)
        elif prefix == '-l':
            options_dict['libraries'].append(rest)
        else:
            options_dict['extra_compile_args'].append(comp)

    commandLine = "%s --variable=libdir %s" % (command, components)
    output = get_command_output(commandLine).strip()

    return options_dict

my_ext = \
    Extension("fixedliststore",
              [
               'fixed-list-store.c',
               'fixed-list-store-module.c',
               'fixed-list-store-wrapper.c',
              ],
              **parse_pkg_config('pkg-config',
                                 'pygobject-2.0 gtk+-2.0 glib-2.0 gthread-2.0')
    )

#### Run setup ####
setup(name='miro',
    version='1.0',
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getmiro.com/',
    download_url='http://www.getmiro.com/downloads/',
    ext_modules=[my_ext],
)
