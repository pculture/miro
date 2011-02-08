# Miro - an RSS based video player application
# Copyright (C) 2011
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

import logging
import subprocess
import tempfile
import re
import os
import select
import threading

from miro import util
from miro.plat.utils import (get_ffmpeg_executable_path, setup_ffmpeg_presets,
                             thread_body)

# Transcoding
#
# The basic operation of transcoding is pretty simple.  The client
# determines whether it needs a transcode by looking at the metadata
# that came with the songlist (for example, for daap, this is
# daap.songformat).  If it needs a transcode, it requests a m3u8 file
# which contains chunks of mpegts that may be transcoded on the fly.
#
# This scheme does mean that the client cannot receive m3u8 files, but
# I don't think that's important.  If it becomes an issue, I suppose we could
# update the protocol to add a special http query string to indicate a 
# forced transcode.
#
# Future work: maybe hook directly into the ffmpeg libraries, then we
# don't need to parse.

container_regex = re.compile('mov,mp4,m4a,3gp,3g2,mj2,')
duration_regex = re.compile('Duration: ')
has_video_regex = re.compile('Stream.*: Video')
has_audio_regex = re.compile('Stream.*: Audio')

def needs_transcode(media_file):
    """needs_transcode()

    Returns (False, None) if no need to transcode.
    Returns (True, info) if there is a need to transcode.

    where info is

    (duration, has_audio, has_video)

    The duration is transmitted for transcoding purposes because we need to
    build a m3u8 playlist and what we get out of the Miro database may be 
    unreliable (does not exist).

    May throw exception if ffmpeg not found.  Remember to catch."""
    ffmpeg_exe = get_ffmpeg_executable_path()
    kwargs = {"stdout": subprocess.PIPE,
              "stderr": subprocess.PIPE,
              "stdin": subprocess.PIPE,
              "startupinfo": util.no_console_startupinfo()}
    if os.name != "nt":
        kwargs["close_fds"] = True
    args = [ffmpeg_exe, "-i", media_file]
    handle = subprocess.Popen(args, **kwargs)
    # XXX unbounded read here but should be okay, ffmpeg output is finite.
    # note that we need to read from stderr, since that's what ffmpeg spits 
    # out.
    text = handle.stderr.read()
    if container_regex.search(text):
        transcode = False
    else:
        transcode = True
    # "    Duration: XX:XX:XX.XX, ..."
    match = duration_regex.search(text)
    start, end = match.span()
    duration_start = text[end:]
    duration = duration_start[:duration_start.index(',')]
    # Convert to seconds.  We can't handle fractions of a second so 
    # skip over those bits.
    hours, minutes, seconds = duration.split(':')
    # Strip the fractional seconds.  Always round up, then we won't miss
    # any data.
    seconds = int(float(seconds) + 0.5)
    seconds += int(minutes) * 60
    seconds += int(hours) * 3600
    has_audio = has_audio_regex.search(text)
    has_video = has_video_regex.search(text)

    return (transcode, (seconds, has_audio, has_video))

# How does the transcoding pipeline work?
#
# A media object that needs to be transcoded is basically represented
# by a TranscodeObject.  This encapsulates the media file, and the
# actual commands that need to be run to spit out something that's
# playable.
#
# At the moment, the thing that would probably work for everybody is
# H.264 with aac audio (video + audio) or mp3 (audio only) wrapped
# inside a mpegts container.  mpegts is used because it allows for 
# live streaming (and hence, transcoding), without the need for 
# a file container.  Many file containers are actually not suitable
# because they the ability to seek on the output, something you cannot
# readily do over a socket.  The playlist is built manually.
#
# There are basically two components with this: first is the actual
# transcode (currently, via FFmpeg) and segmentation (to split the mpegts
# into mpegts segments) via the segmenter program.  The chunks are labeled
# sequentially and start from 0.  The basic arguments of the segmenter that 
# you'd probably want to play with is the duration.
#
# Now, to the actual pipeline.  When FFmpeg transcodes, output is transmitted
# to the writable end of a pipe.  The readable end is connected to the
# input of the segmenter program.  2 pipes are connected to the main 
# Miro program: the control pipe and the data pipe.  The data pipe handles
# outputting the actual mpegts segments while the control pipe handles
# the signaling.  This mainly allows for two things: (1) to allow the segmenter
# signal when data is ready, and (2) for throttling.  One advantage of this
# scheme is there is no need to deal with temporary files on the filesystem.
# Once a chunk is sent to the client, it is thrown away.
#
# When a client seeks to a position that is not in its current playing chunk
# and does not have the seeked-to chunk in its cache, it may request
# the chunk from the server.  In this case, the current transcode operation
# stops, and a new transcode operation begins at the requested time offset
# calculated based on which chunk was requested.
class TranscodeObject(object):
    """TranscodeObject

    This object represents a media item which needs to be transcoded.

    For video files, H.264 and AAC (if audio track present) in mpegts
    container (using libx264 and aac)

    For audio files, mp3 format (using libmp3lame).

    This is meant to be a use-once object.  Create, transcode, discard.

    conversions.py is too specialized for what it does, so, hence there may
    be some duplication here.
    """

    time_offset_args = ['-ss']
    # XXX these bitrate qualities are hardcoded
    #has_video_args = ['-vcodec', 'libx264', '-sameq', '-vpre', 'ipod640',
    #                  '-vpre', 'slow']
    #has_video_has_audio_args = ['-acodec', 'aac', '-strict', 'experimental',
    #                  '-ab', '160k', '-ac', '2']
    has_video_args = []
    has_video_has_audio_args = []
    has_audio_args = ['-acodec', 'libmp3lame', '-ac', '2', '-ab', '160k']
    #video_output_args = ['-f mpegts', '-']
    video_output_args = ['-f', 'mpeg', '-']
    audio_output_args = ['-f', 'mpegts', '-']

    segment_duration = 10
    segmenter_args = ['-', str(segment_duration)]

    buffer_high_watermark = 6

    def __init__(self, media_file, itemid, media_info, request_path_func):
        self.media_file = media_file
        self.time_offset = 0
        duration, has_audio, has_video = media_info
        self.duration = duration
        self.itemid = itemid
        self.has_audio = has_audio
        self.has_video = has_video
        # This setting makes the environment global to the app instead of
        # the subtask.  But I guess that's okay.
        setup_ffmpeg_presets()
        self.ffmpeg_handle = self.segmenter_handle = None

        self.request_path_func = request_path_func

        self.nchunks = self.duration / TranscodeObject.segment_duration
        self.trailer = self.duration % TranscodeObject.segment_duration
        if self.trailer:
            self.nchunks += 1
        print 'TRANSCODE INFO, duration', self.duration
        print 'TRANSCODE INFO, nchunks ', self.nchunks
        print 'TRANSCODE INFO, trailer', self.trailer

        # XXX dodgy
        # Set start_chunk != current_chunk to force seek() to return True
        self.current_chunk = -1
        self.start_chunk = 0
        self.chunk_buffer = []
        self.chunk_lock = threading.Lock()
        # TODO Make sure the semaphore cannot grow past the high watermark
        self.chunk_sem = threading.Semaphore(0)
        self.terminate_signal_thread = False
        self.create_playlist()

    def create_playlist(self):
        self.playlist = ''
        self.playlist += '#EXTM3U\n'
        self.playlist += ('#EXT-X-TARGETDURATION:%d\n' % 
                          TranscodeObject.segment_duration)
        self.playlist += '#EXT-X-MEDIA-SEQUENCE:0\n'
        for i in xrange(self.nchunks):
            # XXX check corner case
            # Special case
            if i == (self.nchunks - 1) and self.trailer:
                chunk_duration = self.trailer
            else:
                chunk_duration = self.segment_duration
            self.playlist += '#EXTINF:%d,\n' % chunk_duration
            urlpath = self.request_path_func(self.itemid, 'ts')
            # This returns us a pedantically correct path but we want to be
            # able to use http, which is understood by everybody and is 
            # what's used by the underlying.
            urlpath = urlpath.replace('daap://', 'http://')
            # Append our chunk XXX - bad way to append a query like this
            urlpath += '&chunk=%d' % i
            self.playlist += urlpath + '\n'
        self.playlist += '#EXT-X-ENDLIST\n'
        print 'PLAYLIST', self.playlist

    def get_playlist(self):
        fildes, name = tempfile.mkstemp()
        os.unlink(name)
        os.write(fildes, self.playlist)
        os.lseek(fildes, 0, os.SEEK_SET)
        return fildes

    def seek(self, chunk):
        # Is it requesting the next available chunk in the sequence?  If so
        # then it's fine, nothing to do.  Otherwise, stop the job.  Returns
        # a booelan indicating whether a transcode needs to be restarted.
        if self.current_chunk == chunk:
            return False
        self.time_offset = chunk * TranscodeObject.segment_duration
        self.shutdown()
        # XXX FIXME: should only clear if this is a real seek
        # Clear the chunk buffer, and the lock/synchronization state
        self.start_chunk = self.current_chunk = chunk
        self.chunk_buffer = []
        self.chunk_lock = threading.Lock()
        self.chunk_sem = threading.Semaphore(0)
        # OK, you can restart the transcode by calling transcode()
        return True

    def transcode(self):
        self.r, self.child_w = os.pipe()
        self.child_r, self.w = os.pipe()
        ffmpeg_exe = get_ffmpeg_executable_path()
        kwargs = {#"stdin": open(os.devnull, 'rb'),
                  "stdout": subprocess.PIPE,
                  #"stderr": open(os.devnull, 'wb'),
                  "startupinfo": util.no_console_startupinfo()}
        if os.name != "nt":
            kwargs["close_fds"] = True
        args = [ffmpeg_exe, "-i", self.media_file]
        if self.time_offset:
            args += TranscodeObject.time_offset_args + [str(self.time_offset)]
        if self.has_video:
            args += TranscodeObject.has_video_args
            if self.has_audio:
                # A/V transcode
                args += TranscodeObject.has_video_has_audio_args
            args += TranscodeObject.video_output_args
        elif self.has_audio:
            args += TranscodeObject.has_audio_args
            args += TranscodeObject.audio_output_args
        else:
           raise ValueError('no video or audio stream present')

        print 'Running command ', ' '.join(args)
        self.ffmpeg_handle = subprocess.Popen(args, **kwargs)

        # XXX
        segmenter_exe = '/Users/glee/segmenter'
        args = [segmenter_exe]
        child_fds = [str(self.child_r), str(self.child_w)]
        args += TranscodeObject.segmenter_args + child_fds
        kwargs = {"stdout": subprocess.PIPE,
                  "stdin": self.ffmpeg_handle.stdout,
                  #"stderr": open(os.devnull, 'wb'),
                  "startupinfo": util.no_console_startupinfo()}
        # XXX Can't use this - need to pass on the child fds
        #if os.name != "nt":
        #    kwargs["close_fds"] = True

        print 'Running command ', ' '.join(args)
        self.segmenter_handle = subprocess.Popen(args, **kwargs)

        self.thread = threading.Thread(target=thread_body,
                                       args=[self.signal_thread],
                                       name="Transcode Signaling")
        self.thread.start()

    def signal_thread(self):
        i = self.start_chunk
        while i < self.nchunks and not self.terminate_signal_thread:
            data = ''
            rset = [self.segmenter_handle.stdout, self.r]
            while True:
                #print 'SELECT'
                r, w, x = select.select(rset, [], [])
                # 3 cases when we wake up and r is not empty:
                # both are readable: read segmenter handle, read self.r then
                # continue to next file.
                #
                # segmenter handle only: read segmenter handle then select
                # again
                #
                # self.r only: read self.r and then continue to next file
                next_file = False
                #if self.segmenter_handle.stdout in r:
                #    print 'SEGMENTER DATA READABLE'
                #if self.r in r:
                #    print 'CONTROL PIPE READABLE'
    
                if self.segmenter_handle.stdout in r:
                    # Bounded read, stdout doesn't close until the program 
                    # does!  Also, do a manual read because the stdout file
                    # object is broken and won't return a short read.
                    d = os.read(self.segmenter_handle.stdout.fileno(), 1024)
                    # EOF so we can break without normal restart throttle proto
                    if not d:
                        break
                    data += d
                if self.r in r:
                    throwaway = os.read(self.r, 1024)
                    next_file = True
                if next_file:
                    os.write(self.w, 'b')
                    break
            # XXX what to do?  can block in the semaphore
            if self.terminate_signal_thread:
                break
            self.chunk_lock.acquire()
            fildes, name = tempfile.mkstemp()
            os.unlink(name)
            os.write(fildes, data)
            os.lseek(fildes, 0, os.SEEK_SET)
            print 'APPEND', fildes
            self.chunk_buffer.append(fildes)
            i += 1
            self.chunk_lock.release()
            # Tell consumer there is stuff available
            self.chunk_sem.release()

    def get_chunk(self):
        # XXX How do we save a reference to this guy?  discard_chunk?
        # ANS: wrap around file wrapper would be good thing to do
        # Consume an item ...
        self.chunk_sem.acquire()
        self.chunk_lock.acquire()
        fildes = self.chunk_buffer[0]
        self.current_chunk += 1
        self.chunk_buffer = self.chunk_buffer[1:]
        print 'POP'
        self.chunk_lock.release()
        print 'FILDES %d' % fildes
        return fildes

    # Shutdown the transcode job.  If we quitting, make sure you call this
    # so the segmenter et al have a chance to clean up.
    def shutdown(self):
        # We only need to kill the last guy in the pipe ... and wait for
        # the signaling thread to finish.  The signaling thread read will
        # return 0, and go back to the top-level loop where it will know 
        # it needs to quit.  We wait for the quit to happen.
        if self.segmenter_handle:
            self.segmenter_handle.terminate()
            self.terminate_signal_thread = True
            # Make sure we wakeup the semaphore, if we are stuck in there.
            # The synchronization watermarks doesn't matter anymore since
            # we are going away.
            self.chunk_sem.release()
            self.signal_thread.join()
            self.terminate_signal_thread = False
            self.segmenter_handle = None
            self.ffmpeg_handle = None
