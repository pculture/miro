# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

"""``miro.metadataprogress`` -- Send the frontend metadata progress updates
"""

import logging

from miro import eventloop
from miro import filetypes
from miro import messages

class MetadataProgressUpdater(object):
    """Send the frontend progress updates for extracting metadata.


    This class gets put in app.metadata_progress_updater.  It should be used
    for operations that create lots of FileItems.

    To use this class, call will_process_path() before creating any of the
    FileItems for all the paths you will add.  Then the moviedata.py calls
    path_processed() once all of the metadata processing is done.
    """
    def __init__(self):
        # maps target type -> counts
        self.total = {}
        self.remaining = {}
        # maps path -> target key
        self.path_to_target = {}
        # targets that we need to update the frontend about
        self.targets_to_update = set()
        # handle for our delayed callback
        self.timeout = None
        # by default, wait 2 seconds before sending the progess update to
        # the frontend
        self.message_interval = 2.0

    def _guess_mediatype(self, path):
        """Guess the mediatype of a file. Needs to be quick, as it's executed
        by the requesting thread in request_update(), and nothing will break
        if it isn't always accurate - so just checks filename.
        """
        if filetypes.is_video_filename(path):
            mediatype = 'video'
        elif filetypes.is_audio_filename(path):
            mediatype = 'audio'
        else:
            mediatype = 'other'
        return mediatype

    def _calc_target(self, path, device):
        """Calculate the target to use for our messages.  """

        mediatype = self._guess_mediatype(path)
        if device:
            return (u'device', '%s-%s' % (device.id, mediatype))
        elif mediatype in ('audio', 'video'):
            return (u'library', mediatype)
        else: # mediatype 'other'
            return None

    @eventloop.as_idle
    def will_process_path(self, path, device=None):
        """Call we've started processing metadata for a file

        This method executes as an idle callback, so it's safe to call from
        any thread.
        """
        self._will_process_path(path, device)

    @eventloop.as_idle
    def will_process_paths(self, paths, device=None):
        """Call we've started processing metadata for several files.  The
        advantage to this method is that it only adds one idle callback for the
        whole set of filenames.

        This method executes as an idle callback, so it's safe to call from
        any thread.
        """
        for path in paths:
            self._will_process_path(path, device)
        
    def _will_process_path(self, path, device=None):
        """Actual implementation of the logic to add a new path to the metadata
        queue.
        """
        if path in self.path_to_target:
            # hmm, we already are storing path in our system.  Log a
            # warning and don't count it
            logging.warn("MetadataProgressUpdate.will_process_path() "
                         "called for path %s that we already "
                         "counted for %s", path,
                         self.path_to_target[path])
            return
        target = self._calc_target(path, device)
        if target is None:
            return

        self.path_to_target[path] = target
        self.total.setdefault(target, 0)
        self.total[target] += 1
        self.remaining.setdefault(target, 0)
        self.remaining[target] += 1
        self._schedule_update(target)

    @eventloop.as_idle
    def path_processed(self, path):
        """Call we've finished all processing for a file.

        This method executes as an idle callback, so it's safe to call from
        any thread.
        """
        try:
            target = self.path_to_target.pop(path)
        except KeyError:
            # will_process_path wasn't called, just ignore
            return

        self.remaining[target] -= 1
        if not self.remaining[target]:
            # finished extracting all data, reset the total
            self.total[target] = 0
        self._schedule_update(target)

    def _schedule_update(self, target):
        self.targets_to_update.add(target)
        if self.timeout is None:
            self.timeout = eventloop.add_timeout(self.message_interval,
                    self._send_updates, "update metadata progress")

    def _send_updates(self):
        for target in self.targets_to_update:
            update = messages.MetadataProgressUpdate(target,
                    self.remaining[target], None, self.total[target])
            update.send_to_frontend()
        self.targets_to_update = set()
        self.timeout = None
