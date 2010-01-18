# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

# Make sure we can load the modules that Py2exe bundles for us
import sys
exe = sys.executable
exe_dir = exe[:exe.rfind('\\')]
sys.path.append(exe_dir + '\\library.zip')

import urllib
import ctypes
from ctypes import byref
import glob
import os
import sys
from time import sleep, time

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002

# load the DLL
libvlc = ctypes.cdll.libvlc
# set up the function signatures
libvlc.libvlc_new.restype = ctypes.c_void_p
libvlc.libvlc_media_player_new.restype = ctypes.c_void_p
libvlc.libvlc_media_new.restype = ctypes.c_void_p
libvlc.libvlc_media_player_get_length.restype = ctypes.c_longlong
libvlc.libvlc_media_player_get_position.restype = ctypes.c_float
libvlc.libvlc_exception_init.restype = None

class VLCException(ctypes.Structure):
    _fields_ = [
            ('b_raised', ctypes.c_int),
            ('i_code', ctypes.c_int),
            ('psz_message', ctypes.c_char_p)
    ]

exception = VLCException() 
# global exception object

libvlc.libvlc_exception_init(byref(exception))

class VLCError(Exception):
    pass

def check_exception():
    if exception.b_raised:
        code = exception.i_code
        msg = exception.psz_message
        libvlc.libvlc_exception_clear(byref(exception))
        raise VLCError("%s: %s" % (code, msg))

def make_string_list(*args):
    ArgsArray = ctypes.c_char_p * len(args)
    return ArgsArray(*args)

def init_vlc(*args):
    arg_pointers = make_string_list(*args)
    vlc = libvlc.libvlc_new(len(arg_pointers), arg_pointers, byref(exception))
    check_exception()
    return vlc

def wait_for_play(media_player):
    # FIXME - this is terrible; switch to event handling.
    while True:
        state = libvlc.libvlc_media_player_get_state(media_player, 
                                                     byref(exception))
        check_exception()
        if state in (3, 6, 7):
            # Break on the PLAYING, ENDED or ERROR states
            break
        else:
            sleep(0.1)

def get_type(media_player):
    video_tracks = libvlc.libvlc_video_get_track_count(media_player, 
            byref(exception))
    try:
        check_exception()
    except VLCError:
        video_tracks = 0
    audio_tracks = libvlc.libvlc_audio_get_track_count(media_player,
            byref(exception))
    try:
        check_exception()
    except VLCError:
        audio_tracks = 0

    if video_tracks > 0:
        return 'video'
    elif audio_tracks > 0:
        return 'audio'
    else:
        return 'other'

def make_snapshot(video_path, thumbnail_path):
    if os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)

    if isinstance(video_path, unicode):
        video_path = video_path.encode("utf-8")
    video_path = urllib.quote(video_path)

    mrl = 'file:///%s' % video_path

    vlc = init_vlc( "vlc", "--noaudio", 
            '--vout', 'dummy', 
            '--no-video-title-show',
            '--quiet', '--nostats', '--intf', 'dummy', 
            '--plugin-path', 'vlc-plugins')

    media_player = libvlc.libvlc_media_player_new(vlc, 
                                                  byref(exception))
    check_exception()
    media = libvlc.libvlc_media_new(vlc, 
                                    ctypes.c_char_p(mrl),
                                    byref(exception))
    check_exception()

    libvlc.libvlc_media_player_set_media(media_player, 
                                         media,
                                         byref(exception))
    check_exception()
    libvlc.libvlc_media_player_play(media_player, 
                                    byref(exception))
    check_exception()

    wait_for_play(media_player)
    length = libvlc.libvlc_media_player_get_length(media_player, 
                                                   byref(exception))
    check_exception()

    media_type = get_type(media_player)

    libvlc.libvlc_media_player_set_position(media_player, 
                                            ctypes.c_float(0.5),
                                            byref(exception))
    check_exception()

    # allow a little time for VLC to seek
    sleep(0.5)

    # if it's a video, take a snapshot
    if media_type == "video":
        libvlc.libvlc_video_take_snapshot(media_player, 
                                          ctypes.c_char_p(thumbnail_path),
                                          ctypes.c_int(0), 
                                          ctypes.c_int(0),
                                          byref(exception))
        check_exception()

        # allow a little time for VLC to take the snapshot
        sleep(0.5)

    # if the length didn't work out before, we try it again
    # FIXME - we can probably remove this when we switch to
    # event handling in wait_for_play.
    if length <= 0:
        length = libvlc.libvlc_media_player_get_length(media_player, 
                                                       byref(exception))
        check_exception()

    libvlc.libvlc_media_player_stop(media_player, byref(exception))
    check_exception()

    libvlc.libvlc_media_player_set_media(None, byref(exception))
    check_exception()

    libvlc.libvlc_media_release(media)
    libvlc.libvlc_media_player_release(media_player)
    libvlc.libvlc_release(vlc)

    print "Miro-Movie-Data-Length: %d" % length
    if os.path.exists(thumbnail_path):
        print "Miro-Movie-Data-Thumbnail: Success"
    else:
        print "Miro-Movie-Data-Thumbnail: Failure"
    print "Miro-Movie-Data-Type: %s" % media_type

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print "moviedata_util <video_path> <thumbnail_path>"
        sys.exit(0)

    try:
        # disable annoying windows popup
        ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX | 
                SEM_FAILCRITICALERRORS)
        make_snapshot(sys.argv[1], sys.argv[2])
    except Exception, e:
        import traceback
        traceback.print_exc()
        print "Miro-Movie-Data-Length: -1"
        print "Miro-Movie-Data-Thumbnail: Failure"
