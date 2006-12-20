#!/usr/bin/env python
#
# Nightly build script for Democracy Player Windows port
# Copyright (c) 2006 Participatory Culture Foundation
#
# Licensed under the terms of the GNU GPL 2.0 or later
#

import sys
import shutil
import os
import re
import os.path

orig_dir = os.getcwd()
repository_url = "https://svn.participatoryculture.org/svn/dtv/trunk/"

def die(error = "An error occured", code = 1):
    try:
        print "ERROR: %s" % error
        os.chdir(orig_dir)
    finally:
        sys.exit(code)

def chdir_or_die(path):
    try:
        os.chdir(path)
    except:
        die("Cannot change current directory to %s" % path)

def checkout_and_update(repository, build_dir):
    full_dir = os.path.join(build_dir, repository)
    full_url = repository_url + repository
    if os.path.isdir(repository):
        print "Updating %s..." % repository
        sys.stdout.flush()
        chdir_or_die(full_dir)
        try:
            if (os.system("svn --non-interactive update")):
                die("SVN update of %s failed" % repository)
        except:
            die("Error running svn update of %s" % repository)
        chdir_or_die(build_dir)
    else:
        print "Checking out %s..." % repository
        sys.stdout.flush()
        chdir_or_die(build_dir)
        try:
            if (os.system("svn --non-interactive co %s" % full_url)):
                die("SVN update of %s failed" % repository)
        except:
            die("Error running svn check out of %s" % repository)

def find_installer_name():
    for filename in os.listdir(os.path.join(platform_build_dir,"dist")):
        if re.match(installer_filename, filename):
            return filename
    return None

# Eventually, this build script will work for all supported platforms
#
# For now, I'm hardcoding these variables
platform = "windows-xul"
repositories = ["tv","dtv-binary-kit"]
build_command = "bdist_xul"
installer_filename = "Democracy-[0-9.]+\.exe"

# Find the build directory
if len(sys.argv) <= 1:
    die ("Usage: %s <build directory>" % sys.argv[0])

root_dir = os.path.normpath(sys.argv[1])
build_dir = os.path.join(root_dir, "build")
platform_build_dir = os.path.join(build_dir,"tv","platform",platform)

if not os.path.isdir(root_dir):
    die("%s is not a directory" % root_dir)

chdir_or_die(root_dir)

if not os.path.isdir(build_dir):
   try:
       os.mkdir(build_dir)
   except:
       die("Cannot create %s" % build_dir)

chdir_or_die(build_dir)

for repository in repositories:
    checkout_and_update(repository, build_dir)

chdir_or_die(platform_build_dir)

try:
    if (os.system("python setup.py clean")):
        die("Clean failed")
except:
    die("Cannot clean build directory")

try:
    if (os.system("python setup.py %s" % build_command)):
        die("Build failed")
except:
    die("Cannot run build")

installer = find_installer_name()
if installer is None:
    die("Can't find the installer!")

try:
    shutil.copyfile(os.path.join(platform_build_dir,"dist",installer),
                    os.path.join(root_dir, installer))
except:
    die("Can't copy the installer!")

chdir_or_die(orig_dir)