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
import re
import os

from miro import util
from miro.plat.utils import get_ffmpeg_executable_path, setup_ffmpeg_presets

# Transcoding
#
# Currently this is only supported for the iPad, so the operations
# are pretty basic.
#
# * Do a dry run of ffmpeg.  This gives us the actual container
#   format of the file, as the database is sometimes unreliable.
#   Imported files (ones that are not downloaded) do not have the
#   mime info, so we can't rely on that.  Sometimes files do not have
#   enclosure_format, so we can't rely on that either.  And finally
#   sometimes files do not have a valid extension, do we can't
#   rely on that.  Also, pick out the duration.  We need to do a couple
#   of regexp do read that information.
#
# * If it's the mov/mp4/m4a etc, send that out directly.  This is 
#   iPad native stuff, so it should be able to deal.
#
# * Otherwise, transcode to h.264 using mpegts (video) or mp3 (audio).
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
    kwargs = {"bufsize": 1,
              "stdout": subprocess.PIPE,
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

    time_offset_args = ['-t']
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

    def __init__(self, media_file, media_info):
        self.media_file = media_file
        self.time_offset = 0
        duration, has_audio, has_video = media_info
        self.duration = duration
        self.has_audio = has_audio
        self.has_video = has_video
        # I need to rewrite the m3u8 anyway because I need to tack on the
        # session-id and all that.
        self.segmenter_args = ['-', TranscodeObject.segment_duration,
                               media_file]
        # This setting makes the environment global to the app instead of
        # the subtask.  But I guess that's okay.
        setup_ffmpeg_presets()
        self.ffmpeg_handle = self.segmenter_handle = None

        self.prefix = None
        self.query = None

        self.nchunks = self.duration / TranscodeObject.segment_duration
        self.trailer = self.duration % TranscodeObject.segment_duration
        if self.trailer:
            self.nchunks += 1

        self.create_playlist()

    def create_playlist(self):
        self.playlist = ''
        self.playlist += '#EXTM3U\n'
        self.playlist += ('#EXT-X-TARGETDURATION:%d\n' % 
                          TranscodeObject.segment_duration)
        for i in xrange(self.nchunks):
            path = (self.prefix + '/' + self.media_file + '-' + i + '.ts' +
                    '?' + self.query)
            self.playlist = '#EXTINF:%d,\n' % self.duration
            # XXX check corner case
            # Special case
            if i == self.nchunks and self.trailer:
                self.playlist = self.trailer
            self.playlist += path
        self.playlist += '#EXT-X-ENDLIST\n'

    def playlist(self):
        return self.playlist

    def seek(self, chunk):
        # Strip off the prefix
        self.time_offset = chunk * TranscodeObject.segment_duration
        # We only need to kill the last guy in the pipe ...
        if self.segmenter_handle:
            self.segmenter_handle.terminate()
        # OK, you can restart the transcode by calling transcode()

    def transcode(self):
        ffmpeg_exe = get_ffmpeg_executable_path()
        kwargs = {"stdin": open(os.devnull, 'rb'),
                  "stdout": subprocess.PIPE,
                  "stderr": open(os.devnull, 'wb'),
                  "startupinfo": util.no_console_startupinfo()}
        if os.name != "nt":
            kwargs["close_fds"] = True
        args = [ffmpeg_exe, "-i", self.media_file]
        if self.time_offset:
            args += TranscodeObject.time_offset_args + [self.time_offset]
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
        args += TranscodeObject.segmenter_args
        kwargs = {"stdout": self.ffmpeg_handle.stdout,
                  "stdin": open(os.devnull, 'rb'),
                  "stderr": open(os.devnull, 'wb'),
                  "startupinfo": util.no_console_startupinfo()}
        if os.name != "nt":
            kwargs["close_fds"] = True

        self.segmenter_handle = subprocess.Popen(args, **kwargs)
        return segmenter_handle.stdout.fileno()
