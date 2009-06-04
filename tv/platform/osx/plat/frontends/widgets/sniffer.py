# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

from QTKit import *

from miro.plat.frontends.widgets import audio
from miro.plat.frontends.widgets import video
from miro.plat.frontends.widgets import quicktime

###############################################################################

class SniffingPlayer (quicktime.Player):
    
    def __init__(self):
        supported_media_types = audio.SUPPORTED_MEDIA_TYPES + video.SUPPORTED_MEDIA_TYPES
        quicktime.Player.__init__(self, supported_media_types)
    
    def get_item_type(self, item_info):
        qtmovie = self.get_movie_from_file(item_info.video_path)
        if qtmovie is None:
            return 'other'

        allTracks = qtmovie.tracks()
        if len(allTracks) == 0:
            return 'other'

        has_audio = False
        has_video = False
        for track in allTracks:
            media_type = track.attributeForKey_(QTTrackMediaTypeAttribute)
            if media_type in audio.SUPPORTED_MEDIA_TYPES:
                has_audio = True
            elif media_type in video.SUPPORTED_MEDIA_TYPES:
                has_video = True
        
        item_type = 'other'
        if has_video:
            item_type = 'video'
        elif has_audio and not has_video:
            item_type = 'audio'

        logging.debug("Item type set to: %s" % item_info.file_type)
        logging.debug("Item type checked by sniffing: %s" % item_type)
        return item_type
        
###############################################################################
    
sniffer = SniffingPlayer()
def get_item_type(item_info):
    return sniffer.get_item_type(item_info)

###############################################################################
