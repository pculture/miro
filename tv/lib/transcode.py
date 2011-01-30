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
from miro.plat.utils import get_ffmpeg_executable_path

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
    text =  handle.stderr.read()
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

    # XXX these bitrate qualities are hardcoded
    has_video_has_audio_args = ['-vcodec', 'libx264', '-sameq']
    has_video_args = ['-acodec', 'aac', '-strict', 'experimental',
                      '-ab', '160k']
    has_audio_args = ['-acodec', 'libmp3lame', '-ab', '160k']
    video_output_args = ['-f mpetgs', '-']
    audio_output_args = ['-']

    def __init__(self, media_file, time_offset, media_info):
        self.media_file = media_file
        self.time_offset = time_offset
        duration, has_audio, has_video = media_info
        self.duration = duration
        self.has_audio = has_audio
        self.has_video = has_video

    def transcode(self):
        ffmpeg_exe = get_ffmpeg_executable_path()
        kwargs = {"bufsize": 1,
                  "stdout": subprocess.PIPE,
                  "stderr": subprocess.PIPE,
                  "stdin": subprocess.PIPE,
                  "startupinfo": util.no_console_startupinfo()}
        if os.name != "nt":
            kwargs["close_fds"] = True
        args = [ffmpeg_exe, "-i", self.media_file]
        if self.video:
            args += TransodeObject.has_video_args
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
        handle = subprocess.Popen(args, **kwargs)
        return handle.stdout
