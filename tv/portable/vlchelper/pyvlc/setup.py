from distutils.core import setup, Extension
import os

def get_cflags():
    vlcconfig=None
    for n in ( 'vlc-config',
               os.path.sep.join( ('..', 'vlc-config' ))):
        if os.path.exists(n):
            vlcconfig=n
            break
    if vlcconfig is None:
        print "*** Warning *** Cannot find vlc-config"
        return []
    else:
        cflags=os.popen('%s --cflags' % vlcconfig, 'r').readline().rstrip().split()
        return cflags

# To compile in a local vlc tree
vlclocal = Extension('vlc',
                sources = ['vlcmodule.c', 'mediacontrol-init.c', 'mediacontrol-core.c'],
                include_dirs = ['../include', '../'],
                libraries = ['vlc', 'rt', 'dl' , 'pthread',  'm',
                             'i420_rgb_mmx','i420_yuy2_mmx','i420_ymga_mmx',
                             'i422_yuy2_mmx',
                             'avcodec', 'avformat',
                             'hal', 'dbus-1',
                             'ffmpeg',
                             'mux_ts', 'dvbpsi',
                             'postproc',
                             'memcpymmx', 'memcpymmxext','memcpy3dn',
                             'avcodec',
#                             'x264', 
                             'theora',
                             'faad',                             
                             ],
                extra_objects = [ '/usr/lib/vlc/libfaad.a',
                                  '/usr/lib/libtheora.a',
#                                  '/usr/local/lib/libx264.a',
                                  '/usr/lib/vlc/libx264.a',
#                                  '-lavcodec',
                                  ],
                extra_compile_args = get_cflags(),                     
                library_dirs = [
#    '../lib',
#                                 '../modules/stream_out',
#                                 '../modules/encoder/ffmpeg',
#                                 '../modules/misc/memcpy',
#                                 '../modules/video_chroma',
                                 '../modules/codec/ffmpeg',
                                 '../modules/codec',
                                 '/usr/lib/vlc',
                                 '/usr/lib' ]
                )

# To compile using standard vlc headers and libs in standard places
# (except that we need all headers anyway, since we are compiling
# as a vlc module)
vlcstandard = Extension('vlc',
                sources = ['vlcmodule.c', 'mediacontrol-init.c', 'mediacontrol-core.c'],
                include_dirs = ['../include', '../'],
                libraries = ['vlc', 'rt', 'dl' , 'pthread',  'm',
                             'i420_rgb_mmx','i420_yuy2_mmx','i420_ymga_mmx',
                             'i422_yuy2_mmx',
                             'faad',
                             'hal', 'dbus-1',
                             'theora',
                             'x264',
                             #'stream_out_transcode',
                             'faad',
                             'ffmpeg',
                             'postproc',
                             'memcpymmx', 'memcpymmxext','memcpy3dn', 
                             'avcodec', 'avformat',
                             ],
                extra_compile_args = get_cflags(),
                extra_objects = [ '/usr/lib/libtheora.a',
                                  '/usr/local/lib/libx264.a' ],
                library_dirs = [ '/usr/lib/vlc', '/usr/lib' ],
                )

# To compile in a local vlc tree on Windows
vlcwindows = Extension('vlc',
                sources = ['vlcmodule.c', 'mediacontrol-init.c', 'mediacontrol-core.c'],
                include_dirs = ['../include', '../', '/usr/win32/include' ],
                libraries = ['vlc', 'pthread',  'm', 'intl', 'wsock32', 'iconv',
                	    'memcpymmx', 'memcpymmxext', 'memcpy3dn',
                             'i420_rgb_mmx', 'i420_yuy2_mmx', 'i420_ymga_mmx', 'i422_yuy2_mmx',
                             'ffmpeg', 'avformat', 'z', 'avcodec', 'z', 'faac', 'mp3lame',
                             'mkv', 'matroska',  'winmm'],
                extra_compile_args = get_cflags(),                     
                library_dirs = [ '../lib',
                                 '/usr/win32/lib',
                                 '../modules/stream_out',
                                 '../modules/encoder/ffmpeg',
                                 '../modules/misc/memcpy',
                                 '../modules/video_chroma',
                                 '../modules/codec/ffmpeg',
                                 '../modules/demux'
                                 ]
                )


def guess_extension():
    """Guess the extension to use."""
    ext=None
    if os.sys.platform == 'win32':
        if os.path.exists( os.path.sep.join( ('..',
                                              'include',
                                              'vlc_config.h' ) )):
            print "Using vlcwindows"
            ext=vlcwindows
        else:
            print "*** Error *** The extension should be compiled in a VLC tree."
            os.sys.exit(1)
    else:
        # UNIX platform.
        if os.path.exists( os.path.sep.join( ('..',
                                              'include',
                                              'vlc_config.h' ) )):
            print "Using vlclocal"
            ext=vlclocal
        else:
            print "Using vlcstandard"
            ext=vlcstandard
    return ext

setup (name = 'MediaControl',
       version = '0.8.1-1',
       scripts = [ 'vlcdebug.py' ],
       description = """VLC bindings for python.

This module provides a MediaControl object, which implements an API
inspired from the OMG Audio/Video Stream 1.0 specification. Moreover,
the module provides a Object type, which gives a low-level access to
the vlc objects and their variables.

Example session:

import vlc
mc=vlc.MediaControl(['--verbose', '1'])
mc.playlist_add_item('movie.mpg')

# Start the movie at 2000ms
p=vlc.Position()
p.origin=vlc.RelativePosition
p.key=vlc.MediaTime
p.value=2000
mc.start(p)
# which could be abbreviated as
# mc.start(2000)
# for the default conversion from int is to make a RelativePosition in MediaTime

# Display some text during 2000ms
mc.display_text('Some useless information', 0, 2000)

# Pause the video
mc.pause(0)

# Get status information
mc.get_stream_information()

# Access lowlevel objets
o=vlc.Object(1)
o.info()
i=o.find_object('input')
i.list()
i.get('time')
       """,
       ext_modules = [ guess_extension() ])
