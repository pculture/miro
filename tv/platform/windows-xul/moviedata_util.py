# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

import ctypes
from ctypes import byref
import glob
import os
import sys
from time import sleep, time

path_list = os.environ.get('PATH', '').split(';')
path_list.insert(0, 'plugins')
os.environ['PATH'] = ';'.join(path_list)

# load the DLL
libvlc = ctypes.cdll.libvlc
# set up the function signatures
libvlc.libvlc_new.restype = ctypes.c_void_p
libvlc.libvlc_playlist_get_input.restype = ctypes.c_void_p
libvlc.libvlc_input_get_position.restype = ctypes.c_float
libvlc.libvlc_input_get_length.restype = ctypes.c_longlong

class VLCException(ctypes.Structure):
    _fields_ = [
            ('b_raised', ctypes.c_int),
            ('psz_message', ctypes.c_char_p)
    ]

exception = VLCException() 
# global exception object

libvlc.libvlc_exception_init(byref(exception))

class VLCError(Exception):
    pass

def check_exception():
    if exception.b_raised:
        msg = exception.psz_message
        libvlc.libvlc_exception_clear(byref(exception))
        raise VLCError(msg)

def make_string_list(*args):
    ArgsArray = ctypes.c_char_p * len(args)
    return ArgsArray(*args)

def init_vlc(*args):
    arg_pointers = make_string_list(*args)
    vlc = libvlc.libvlc_new(len(arg_pointers), arg_pointers, byref(exception))
    check_exception()
    return vlc

vlc = init_vlc( "vlc", "--noaudio", 
    '--vout', 'image', 
    '--quiet', '--nostats', '--intf', 'dummy', '--plugin-path', 'vlc-plugins')

def setup_playlist(video_path, thumbnail_path):
    thumb_split = os.path.splitext(thumbnail_path)
    options = make_string_list('image-out-prefix=%s-temp' % thumb_split[0],
            'image-out-format=%s' % thumb_split[1][1:])
    libvlc.libvlc_playlist_add_extended(vlc, video_path, None, len(options),
            options, byref(exception))
    check_exception()
    libvlc.libvlc_playlist_play(vlc, -1, 0, None, byref(exception))
    check_exception()

def wait_for_input():
    while True:
        input = libvlc.libvlc_playlist_get_input(vlc, None)
        if input != None:
            return input

def wait_for_vout(input):
    starttime = time()
    while True:
        if time() - starttime > 4.0:
            return False
        vout_exists = libvlc.libvlc_input_has_vout(input, byref(exception))
        check_exception()
        if vout_exists:
            return True
        sleep(0.1)

def temp_snapshot_path(thumbnail_path, index):
    start, ext = os.path.splitext(thumbnail_path)
    return '%s-temp%.6i%s' % (start, index, ext)

def delete_temp_snapshots(path):
    start, ext = os.path.splitext(path)
    temp_snapshots = glob.glob('%s-temp*%s' % (start, ext))
    for path in temp_snapshots:
        try:
            os.remove(path)
        except:
            pass

def wait_for_snapshot(thumbnail_path):
    while True:
        if os.path.exists(temp_snapshot_path(thumbnail_path, 1)):
            # check for the second snapshot because that means the 1st
            # snapshot is definitely done writing
            os.rename(temp_snapshot_path(thumbnail_path, 0), thumbnail_path)
            break
        input = libvlc.libvlc_playlist_get_input(vlc, None)
        if input is None:
            break
        sleep(0.1)

def stop_input():
    libvlc.libvlc_playlist_clear(vlc, byref(exception))
    check_exception()
    #libvlc.libvlc_playlist_stop(vlc, byref(exception))
    #check_exception()
    while True:
        input = libvlc.libvlc_playlist_get_input(vlc, None)
        if input is None:
            break
        sleep(0.1)

def make_snapshot(video_path, thumbnail_path):
    if os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
    setup_playlist(video_path, thumbnail_path)
    input = wait_for_input()
    libvlc.libvlc_input_set_position(input, ctypes.c_float(0.5), byref(exception))
    check_exception()
    if wait_for_vout(input):
        wait_for_snapshot(thumbnail_path)
    time = libvlc.libvlc_input_get_length(input, byref(exception))
    check_exception()
    stop_input()
    delete_temp_snapshots(thumbnail_path)
    print "Miro-Movie-Data-Length: %d" % (time)
    if os.path.exists(thumbnail_path):
        print "Miro-Movie-Data-Thumbnail: Success"
    else:
        print "Miro-Movie-Data-Thumbnail: Failure"

if __name__ == '__main__':
    try:
        make_snapshot(sys.argv[1], sys.argv[2])
    except Exception, e:
        print e
        print "Miro-Movie-Data-Length: -1"
        print "Miro-Movie-Data-Thumbnail: Failure"
