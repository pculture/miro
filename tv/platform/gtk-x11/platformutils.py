# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################
import os
import config
import prefs
import threading

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

def getAvailableBytesForMovies():
    statinfo = os.statvfs (config.get(prefs.MOVIES_DIRECTORY))
    return statinfo.f_frsize * statinfo.f_bavail

main_thread = None

def setMainThread():
    global main_thread
    main_thread = threading.currentThread()

def confirmMainThread():
    global main_thread
    if main_thread is not None and main_thread != threading.currentThread():
        print "UI function called from thread %s" % (threading.currentThread(),)
        traceback.print_stack()
