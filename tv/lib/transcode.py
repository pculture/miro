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

import errno
import logging
import subprocess
import tempfile
import re
import os
import select
import socket
import sys
import SocketServer
import threading

from miro import app
from miro import util
from miro.plat.utils import (get_ffmpeg_executable_path, setup_ffmpeg_presets,
                             get_segmenter_executable_path, thread_body,
                             get_transcode_video_options,
                             get_transcode_audio_options)

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


class TranscodeManager(object):
    MAX_TRANSCODE_PIPELINES = 5
    def __init__(self):
        self.ffmpeg_event = threading.Event()
        self.ffmpeg_event.set()

    def acquire(self):
        self.ffmpeg_event.wait()
        self.ffmpeg_event.clear()

    def release(self):
        self.ffmpeg_event.set()

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

class TranscodeSinkServer(SocketServer.TCPServer):
    pass

class TranscodeRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        while True:
            try:
                d = self.request.recv(8192)
                self.server.obj.data_callback(d)
                if not d:
                    return
            except socket.error, (err, errstring):
                if err == errno.EINTR:
                    continue
                logging.info('TranscodeRequestHandler err %d desc = %s',
                             err, errstring)
                # Signal EOF
                self.server.obj.data_callback('')
                return

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
    output_args = ['-f', 'mpegts', '-']

    segment_duration = 10
    segmenter_args = [str(segment_duration)]

    # Future work: we only have a high watermark, so the transcode job gets
    # throttled when it reaches the high watermark and then starts again
    # as items are consumed.  It may be good to have a low watermark as well.
    buffer_high_watermark = 6

    def __init__(self, media_file, itemid, media_info, request_path_func):
        self.media_file = media_file
        self.in_shutdown = False
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
        self.transcode_handle = None

        # NB: Explicitly IPv4, FFmpeg does not understand IPv6.
        self.sink = TranscodeSinkServer(('127.0.0.1', 0),
                                           TranscodeRequestHandler)
        self.sink.obj = self

        self.request_path_func = request_path_func

        self.nchunks = self.duration / TranscodeObject.segment_duration
        self.trailer = self.duration % TranscodeObject.segment_duration
        if self.trailer:
            self.nchunks += 1
        logging.debug('TRANSCODE INFO, duration %s' % self.duration)
        logging.debug('TRANSCODE INFO, nchunks %s' % self.nchunks)
        logging.debug('TRANSCODE INFO, trailer %s' % self.trailer)

        # XXX dodgy
        # Set start_chunk != current_chunk to force seek() to return True
        self.current_chunk = -1
        self.start_chunk = 0
        self.chunk_buffer = []
        self.chunk_throttle = threading.Event()
        self.chunk_throttle.set()
        self.chunk_lock = threading.Lock()
        self.chunk_sem = threading.Semaphore(0)
        self.tmp_file = tempfile.TemporaryFile()
        self.create_playlist()
        logging.info('TranscodeObject created %s', self)

    def __del__(self):
        self.shutdown()

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

    def get_playlist(self):
        tmpf = tempfile.TemporaryFile()
        tmpf.write(self.playlist)
        tmpf.flush()
        tmpf.seek(0, os.SEEK_SET)
        return tmpf

    def seek(self, chunk):
        # Is it requesting the next available chunk in the sequence?  If so
        # then it's fine, nothing to do.  Otherwise, stop the job.  Returns
        # a booelan indicating whether a transcode needs to be restarted.
        if self.current_chunk == chunk:
            return False
        self.time_offset = chunk * TranscodeObject.segment_duration
        # XXX special case: new transcode object - don't do any of the below
        # (in fact it wont behave correctly if you do, we try to run shutdown()
        # which will set a shutdown flag ... that's not what we want to do.)
        if self.current_chunk == -1:
            self.current_chunk = 0
            return True
        self.shutdown()
        # Clear the chunk buffer, and the lock/synchronization state
        self.start_chunk = self.current_chunk = chunk
        # TODO: we could turn chunk_buffer into a dictionary or maybe an
        # out of order list of some sort to support implementations that
        # decide to fetch things out of order (possibly by multiple client
        # threads), within reason.
        self.chunk_buffer = []
        self.chunk_lock = threading.Lock()
        self.chunk_sem = threading.Semaphore(0)
        self.chunk_throttle = threading.Event()
        self.chunk_throttle.set()
        self.tmp_file = tempfile.TemporaryFile()
        # OK, you can restart the transcode by calling transcode()
        return True

    def transcode(self):
        app.transcode_manager.acquire()
        try:
            ffmpeg_exe = get_ffmpeg_executable_path()
            kwargs = {"stdin": open(os.devnull, 'rb'),
                      "stdout": subprocess.PIPE,
                      "stderr": open(os.devnull, 'wb'),
                      "startupinfo": util.no_console_startupinfo()}
            if os.name != "nt":
                kwargs["close_fds"] = True
            args = [ffmpeg_exe, "-i", self.media_file]
            if self.time_offset:
                logging.debug('transcode: start job @ %d' % self.time_offset)
                args += TranscodeObject.time_offset_args + [str(self.time_offset)]
            if self.has_video:
                args += get_transcode_video_options()
            if self.has_audio:
                args += get_transcode_audio_options()
            else:
               raise ValueError('no video or audio stream present')
    
            args += TranscodeObject.output_args
            logging.debug('Running command %s' % ' '.join(args))
            self.ffmpeg_handle = subprocess.Popen(args, **kwargs)
    
            segmenter_exe = get_segmenter_executable_path()
            args = [segmenter_exe]
            address, port = self.sink.server_address
            args += TranscodeObject.segmenter_args + [str(port)]
            kwargs = {"stdout": open(os.devnull, 'rb'),
                      "stdin": self.ffmpeg_handle.stdout,
                      "stderr": open(os.devnull, 'wb'),
                      "startupinfo": util.no_console_startupinfo()}
            # XXX Can't use this - need to pass on the child fds
            #if os.name != "nt":
            #    kwargs["close_fds"] = True
    
            logging.debug('Running command %s' % ' '.join(args))
            self.segmenter_handle = subprocess.Popen(args, **kwargs)
   
            self.sink_thread = threading.Thread(target=thread_body,
                                                args=[self.segmenter_consumer],
                                                name="Segmenter Consumer")
            self.sink_thread.daemon = True
            self.sink_thread.start()

            return True
        except StandardError:
            self.transcode_manager.release()
            (typ, value, tb) = sys.exc_info()
            logging.error('ERROR: %s %s' % (str(typ), str(value)))
            return False

    def data_callback(self, d):
        self.tmp_file.write(d)
        if not d:
            self.tmp_file.flush()
            self.tmp_file.seek(0, os.SEEK_SET)
            with self.chunk_lock:
                self.chunk_buffer.append(self.tmp_file)
                chunk_buffer_size = len(self.chunk_buffer)
                if (chunk_buffer_size >= 
                  TranscodeObject.buffer_high_watermark):
                    logging.info('TranscodeObject: throttling')
                    self.chunk_throttle.clear()
            # Tell consumer there is stuff available
            self.chunk_sem.release()
            # ready for next segment
            self.tmp_file = tempfile.TemporaryFile()

    # Data consumer from segmenter.  Here, we listen for incoming request.
    # no need to handle quit signal - the sink should return a zero read
    # when the segmenter goes away.
    def segmenter_consumer(self):
        while True:
            try:
                if self.in_shutdown:
                    app.transcode_manager.release()
                    return
                r, w, x = select.select([self.sink.fileno()], [], [])
                self.chunk_throttle.wait()
                if self.segmenter_handle.poll() is not None:
                    app.transcode_manager.release()
                    return
                try:
                    self.sink.handle_request()
                except socket.error, (err, errstring):
                    # Don't care, wait for EOF
                    pass
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
                raise
            except StandardError:
                raise

    def get_chunk(self):
        # XXX: be sure to add a check to see whether there is an active
        # transcode job or not (also make sure that transcode job isn't
        # inactive because it's already finished
        # XXX How do we save a reference to this guy?  discard_chunk?
        # ANS: wrap around file wrapper would be good thing to do
        # Consume an item ...
        self.chunk_sem.acquire()
        with self.chunk_lock:
            tmpf = self.chunk_buffer[0]
            self.current_chunk += 1
            self.chunk_buffer = self.chunk_buffer[1:]
            self.chunk_throttle.set()
        return tmpf

    # Shutdown the transcode job.  If we quitting, make sure you call this
    # so the segmenter et al have a chance to clean up.
    def shutdown(self):
        # If we kill the segmenter thread, then the stdout and the control
        # pipe reads should return 0.  This can indicate that the transcode
        # pipeline has been terminated.  But how do we know whether it's 
        # a new file or an EOF?  We check whether segmenter has exited.
        # If it has break immediately.  This handles both end of transcode
        # and abortive shutdown.  If we are somewhere in between, we'd 
        # probably be blocked on the read() in the # the handler and that's
        # ok because that should return a zero read when the segmenter goes 
        # away too and that reduces to the select().
        #
        # In case we may be throttled, prod it along by unthrottling.
        # In case we race with get_chunk() (which may run in a different
        # thread), if we clear first, it's ok because that'd have woken it up
        # anyway, and in case they get there first then it's ok too, since
        # we end up unblocking it anyway.
        logging.info('TranscodeObject.shutdown')
        self.in_shutdown = True
        try:
            self.ffmpeg_handle.kill()
            self.segmenter_handle.kill()
            # Wait for segmenter to die so that poll() will return not None
            self.segmenter_handle.wait()
            self.ffmpeg_handle.wait()
            logging.info('TranscodeObject reaping sink')
            self.chunk_throttle.set()
            self.sink_thread.join()
            logging.info('TranscodeObject sink reaped')
            # Set these last: sink thread relies on it.
            self.ffmpeg_handle = None
            self.segmenter_handle = None
            self.sink_thread = None
        # Catch AttributeError in case it's not actually there, or OSError,
        # in case it doesn't exist anymore.  We don't really care.
        # Catch RuntimeError in case sink_thread hasn't been started yet.
        except (RuntimeError, OSError, AttributeError):
            app.transcode_manager.release()
            pass
        self.in_shutdown = False
