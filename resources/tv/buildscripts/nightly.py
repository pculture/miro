#!/usr/bin/env python
#
# Nightly build script for Democracy Player Windows port
# Copyright (c) 2006 Participatory Culture Foundation
#
# Licensed under the terms of the GNU GPL 2.0 or later
#

import sys
import os
import os.path

orig_dir = os.getcwd()
repository_url = "https://svn.participatoryculture.org/svn/dtv/trunk/"

def die(error = "An error occured", code = 1):
    print "ERROR: %s" % error
    os.chdir(orig_dir)
    sys.exit(code)

def checkout_and_update(repository, build_dir):
    full_dir = os.path.join(build_dir, repository)
    full_url = repository_url + repository
    if os.path.isdir(repository):
        try:
            os.chdir(full_dir)
            if (os.system("svn --non-interactive update")):
                die("SVN update of %s failed" % repository)
            os.chdir(build_dir)
        except:
            die("Error running svn update of %s" % repository)
    else:
        try:
            os.chdir(build_dir)
            if (os.system("svn --non-interactive co %s" % full_url)):
                die("SVN update of %s failed" % repository)
        except:
            die("Error running svn check out of %s" % repository)

# Eventually, this build script will work for all supported platforms
#
# For now, I'm hardcoding these variables
platform = "windows-xul"
repositories = ["tv","dtv-binary-kit"]
build_command = "bdist_xul"

# Find the build directory
if len(sys.argv) <= 1:
    die ("Usage: %s <build directory>" % sys.argv[0])

root_dir = os.path.normpath(sys.argv[1])
build_dir = os.path.join(root_dir, "build")

if not os.path.isdir(root_dir):
    die("%s is not a directory" % root_dir)

try:
    os.chdir(root_dir)
except:
    die("Cannot change current directory to %s" % root_dir)

if not os.path.isdir(build_dir):
   try:
       os.mkdir(build_dir)
   except:
       die("Cannot create %s" % build_dir)

try:
    os.chdir(build_dir)
except:
    die("Cannot change current directory to %s" % build_dir)

for repository in repositories:
    checkout_and_update(repository, build_dir)