#!/usr/bin/env python2.4
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
import datetime

orig_dir = os.getcwd()
repository_url = "https://svn.participatoryculture.org/svn/dtv/trunk/"
def die(error = "An error occured", code = 1):
    try:
        print "ERROR: %s" % error
        os.chdir(orig_dir)
    except:
        pass
    sys.exit(code)

# Eventually, this build script will work for all supported platforms
if os.name == 'nt':
    platform = "windows-xul"
    repositories = ["tv","dtv-binary-kit"]
    build_command = "bdist_xul"
    installer_filename = "Democracy-[0-9.]+(-[a-z0-9]+)?\.exe"
    remote_copy_command = "C:\\cygwin\\bin\\scp.exe"
    is_cygwin_command = True
    remote_machine = "pcf2.osuosl.org:/data/pculture/nightlies/"
    installer_extension = "exe"
    python = "python"
elif os.name == 'posix' and os.uname()[0] == 'Darwin':
    platform = "osx"
    repositories = ["tv","dtv-binary-kit-mac"]
    build_command = "py2app -O2 --dist-dir dist/ --force-update --make-dmg"
    installer_filename = "Democracy-[0-9\-]+\.dmg"
    remote_copy_command = "scp -P22"
    is_cygwin_command = False
    remote_machine = "pcf2.osuosl.org:/data/pculture/nightlies/"
    installer_extension = "dmg"
    python = "/usr/local/bin/python2.4"
else:
    die("Unrecognized platform")

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

def remove_old_copies():
   pass 

def cygwinify(path):
    if not is_cygwin_command:
        return path
    else:
        path = os.path.abspath(path).lower().replace("\\","/")
        drive = path[0]
        return "/cygdrive/%s%s" % (drive, path[2:])
        

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

for  repository in repositories:
    checkout_and_update(repository, build_dir)

chdir_or_die(platform_build_dir)

if (os.system("%s setup.py clean" % python)):
    die("Clean failed")

if (os.system("%s setup.py %s" % (python, build_command))):
    die("Build failed")

installer = find_installer_name()
if installer is None:
    die("Can't find the installer!")

try:
    shutil.copyfile(os.path.join(platform_build_dir,"dist",installer),
                    os.path.join(root_dir, installer))
except:
    die("Can't copy the installer!")
 
chdir_or_die(orig_dir)

dest_installer = "Democracy-%4d-%02d-%02d-nightly.%s" % (
                   datetime.date.today().year,
                   datetime.date.today().month,
                   datetime.date.today().day,
                   installer_extension)

upload_cmd = ("%s %s %s%s" %
              (remote_copy_command,
               cygwinify(os.path.join(root_dir,installer)),
               remote_machine, dest_installer))
if os.system(upload_cmd):
    die("Problem uploading build (%s)" % upload_cmd)
