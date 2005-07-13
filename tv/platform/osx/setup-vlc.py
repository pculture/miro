#!/usr/bin/env python

import os
import sys

PATH_TO_VLC_ROOT_FROM_SCRIPT = '../..'

MY_CONFIGURE_ARGS = [
        '--enable-release',
        '--disable-sout',
        '--disable-httpd',
        '--disable-vlm',
        '--disable-gnutls',
        '--disable-livedotcom',
        '--disable-dvdread',
        '--disable-dvdnav',
        '--enable-dvbpsi',
        '--disable-v4l',
        '--disable-libcdio',
        '--disable-libcddb',
        '--disable-cdda',
        '--disable-cddax',
        '--disable-vcd',
        '--disable-satellite',
        '--disable-dvb',
        '--disable-screen',
        '--enable-ogg',
        '--enable-mkv',
        '--disable-mod',
        '--enable-mad',
        '--enable-ffmpeg',
        '--with-ffmpeg-faac',
        '--with-ffmpeg-mp3lame',
        '--with-ffmpeg-zlib',
        '--enable-faad',
        '--disable-toolame',
        '--enable-a52',
        '--enable-dts',
        '--enable-flac',
        '--enable-libmpeg2',
        '--enable-vorbis',
        '--disable-tremor',
        '--enable-speex',
        '--disable-tarkin',
        '--enable-theora',
        '--enable-x264',
        '--enable-cmml',
        '--disable-x11',
        '--disable-xvideo',
        '--disable-glx',
        '--disable-opengl',
        '--disable-sdl',
        '--enable-freetype',
        '--enable-fribidi',
        '--disable-svg',
        '--disable-qte',
        '--disable-hd1000v',
        '--disable-mga',
        '--disable-svgalib',
        '--disable-ggi',
        '--disable-glide',
        '--disable-aa',
        '--disable-caca',
        '--disable-esd',
        '--disable-portaudio',
        '--disable-arts',
        '--disable-alsa',
        '--disable-hd1000a',
        '--disable-skins2',
        '--disable-pda',
        '--disable-wxwindows',
        '--disable-opie',
        '--disable-qnx',
        '--enable-ncurses',
        '--disable-xosd',
        '--disable-visual',
        '--disable-galaktos',
        '--disable-goom',
        '--disable-slp',
        '--disable-lirc',
        '--disable-joystick',
        '--disable-corba',
        '--disable-mozilla',
        '--disable-testsuite',
        ]

if len(sys.argv) != 2:
    print "Usage: %s <path to top of VLC tree containing 'configure'>" % sys.argv[0]
    sys.exit(1)

configFile = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), PATH_TO_VLC_ROOT_FROM_SCRIPT, 'vlc_root'))

vlcRoot = os.path.abspath(sys.argv[1])
print "Absolute path to VLC: %s" % vlcRoot

os.chdir(vlcRoot)
print "*** Running 'bootstrap'"
if os.spawnl(os.P_WAIT, 'bootstrap', 'bootstrap') != 0:
    print "*** VLC 'bootstrap' failed. Check any output above for errors."
    sys.exit(1)
print "*** Running 'configure %s'" % ' '.join(MY_CONFIGURE_ARGS)
confArgs = MY_CONFIGURE_ARGS
confArgs[0:0] = ['configure']
if os.spawnv(os.P_WAIT, 'configure', confArgs) != 0:
    print "*** VLC 'configure' failed. Check any output above for errors."
    sys.exit(1)

print "*** Writing %s" % configFile
f = open(configFile, "w")
f.write(sys.argv[1])
f.close()

print "*** Now run 'make' in %s." % vlcRoot
