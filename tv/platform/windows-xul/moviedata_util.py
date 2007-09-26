import ctypes
from ctypes import byref
import os
import sys
from time import sleep, time

path_list = os.environ.get('PATH', '').split(';')
path_list.insert(0, 'xulrunner\\plugins\\')
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
    '--vout', 'image', '--image-out-replace', 
    '--image-out-prefix', 'C:\\default',
    '--quiet', '--nostats', '--intf', 'dummy', '--plugin-path', 'vlc-plugins')

def setup_playlist(video_path, thumbnail_path):
    thumb_split = os.path.splitext(thumbnail_path)
    options = make_string_list('image-out-prefix=%s' % thumb_split[0],
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
        if time() - starttime > 2.0:
            print 'out of time'
            raise AssertionError("Couldn't get a VOUT")
        vout_exists = libvlc.libvlc_input_has_vout(input, byref(exception))
        check_exception()
        if vout_exists:
            break
        sleep(0.1)

def wait_for_snapshot(path):
    while True:
        if os.path.exists(path):
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
    print 'setup'
    setup_playlist(video_path, thumbnail_path)
    print 'input'
    input = wait_for_input()
    print 'set psoition'
    libvlc.libvlc_input_set_position(input, ctypes.c_float(0.5), byref(exception))
    check_exception()
    print 'vout'
    wait_for_vout(input)
    print 'got vout'
    time = libvlc.libvlc_input_get_length(input, byref(exception))
    check_exception()
    print "Miro-Movie-Data-Length: %d" % (time)
    wait_for_snapshot(thumbnail_path)
    if os.path.exists(thumbnail_path):
        print "Miro-Movie-Data-Thumbnail: Success"
    else:
        print "Miro-Movie-Data-Thumbnail: Failure"
    stop_input()

if __name__ == '__main__':
    try:
        make_snapshot(sys.argv[1], sys.argv[2])
    except Exception, e:
        print e
        print "Miro-Movie-Data-Length: -1"
        print "Miro-Movie-Data-Thumbnail: Failure"
