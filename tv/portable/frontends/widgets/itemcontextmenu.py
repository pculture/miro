# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""itemcontextmenu.py -- Handle poping up an context menu for an item
"""

from miro import app
from miro import messages
from miro.frontends.widgets import share
from miro.gtcache import gettext as _
from miro.gtcache import ngettext

class ItemContextMenuHandler(object):
    """Handles the context menus for rows in an item list."""

    def callback(self, tableview):
        """Callback to handle the context menu.

        This method can be passed into TableView.set_context_menu_callback
        """
        selected = [tableview.model[iter][0] for iter in \
                tableview.get_selection()]
        if len(selected) == 1:
            return self._make_context_menu_single(selected[0])
        else:
            return self._make_context_menu_multiple(selected)

    def _remove_context_menu_item(self, selection):
        """The menu item to remove the item (or None to exclude it)."""
        remove = False
        for info in selection:
            if info.is_external:
                remove = True
                break
        if remove:
            return (_('Remove From the Library'), app.widgetapp.remove_items)
        else:
            return (_('Delete'), app.widgetapp.remove_items)

    def _add_remove_context_menu_item(self, menu, selection):
        remove = self._remove_context_menu_item(selection)
        if remove is not None:
            menu.append(remove)

    def _make_context_menu_single(self, item):
        """Make the context menu for a single item."""
        if item.downloaded:
            def play_and_stop():
                app.playback_manager.start_with_items([item])

            menu = [
                (_('Play'), app.widgetapp.play_selection),
                (_('Play Just this Video'), play_and_stop),
                (_('Add to New Playlist'), app.widgetapp.add_new_playlist),
            ]
            self._add_remove_context_menu_item(menu, [item])
            if item.video_watched:
                menu.append((_('Mark as Unwatched'),
                    messages.MarkItemUnwatched(item.id).send_to_backend))
            else:
                menu.append((_('Mark as Watched'),
                    messages.MarkItemWatched(item.id).send_to_backend))
            if item.expiration_date:
                menu.append((_('Keep'),
                    messages.KeepVideo(item.id).send_to_backend))
            if item.download_info and item.download_info.torrent:
                if item.download_info.state == 'uploading':
                    menu.append((_('Stop seeding'), messages.StopUpload(item.id).send_to_backend))
                else:
                    menu.append((_('Start seeding'), messages.StartUpload(item.id).send_to_backend))
            menu.append((_('Reveal File'),
                lambda : app.widgetapp.open_file(item.video_path)))
        elif item.download_info is not None and item.download_info.state != 'failed':
            menu = [
                    (_('Cancel Download'),
                        messages.CancelDownload(item.id).send_to_backend)
            ]
            if item.download_info.state != 'paused':
                menu.append((_('Pause Download'),
                        messages.PauseDownload(item.id).send_to_backend))
            else:
                menu.append((_('Resume Download'),
                        messages.ResumeDownload(item.id).send_to_backend))
        else:
            menu = [
                (_('Download'),
                    messages.StartDownload(item.id).send_to_backend)
            ]

        menu.append(
            (_('Share'),
             [(_('Email to friend'),
               lambda: share.share_email(item)),
              (_('Post to Video Bomb'),
               lambda: share.share_video_bomb(item)),
              (_('Post to Del.icio.us'),
               lambda: share.share_delicious(item)),
              (_('Post to Digg'),
               lambda: share.share_digg(item)),
              (_('Post to Reddit'),
               lambda: share.share_reddit(item))]))
               
        return menu

    def _make_context_menu_multiple(self, selection):
        """Make the context menu for multiple items."""
        watched = unwatched = downloaded = downloading = available = \
                uploadable = expiring = 0
        for info in selection:
            if info.downloaded:
                downloaded += 1
                if info.video_watched:
                    watched += 1
                    if info.expiration_date:
                        expiring += 1
                else:
                    unwatched += 1
            elif info.download_info is not None:
                downloading += 1
                if (info.download_info.torrent and
                        info.download_info.state != 'uploading'):
                    uploadable += 1
            else:
                available += 1

        menu = []
        if downloaded > 0:
            menu.append((ngettext('1 Downloaded Item',
                                  '%(count)d Downloaded Items',
                                  downloaded,
                                  {"count": downloaded}),
                         None))
            menu.append((_('Play'), app.widgetapp.play_selection)),
            menu.append((_('Add to New Playlist'),
                app.widgetapp.add_new_playlist))
            self._add_remove_context_menu_item(menu, selection)
            if watched:
                def mark_unwatched():
                    for item in selection:
                        messages.MarkItemUnwatched(item.id).send_to_backend()
                menu.append((_('Mark as Unwatched'), mark_unwatched))
            if unwatched:
                def mark_watched():
                    for item in selection:
                        messages.MarkItemWatched(item.id).send_to_backend()
                menu.append((_('Mark as Watched'), mark_watched))
            if expiring:
                def keep_videos():
                    for item in selection:
                        if item.expiration_date:
                            messages.KeepVideo(item.id).send_to_backend()
                menu.append((_('Keep'), keep_videos))

        if available > 0:
            if len(menu) > 0:
                menu.append(None)
            menu.append((ngettext('1 Available Item',
                                  '%(count)d Available Items',
                                  available,
                                  {"count": available}),
                         None))
            def download_all():
                for item in selection:
                    messages.StartDownload(item.id).send_to_backend()
            menu.append((_('Download'), download_all))

        if downloading:
            if len(menu) > 0:
                menu.append(None)
            menu.append((ngettext('1 Downloading Item',
                                  '%(count)d Downloading Items',
                                  downloading,
                                  {"count": downloading}),
                         None))
            def cancel_all():
                for item in selection:
                    messages.CancelDownload(item.id).send_to_backend()
            def pause_all():
                for item in selection:
                    messages.PauseDownload(item.id).send_to_backend()
            menu.append((_('Cancel Download'), cancel_all))
            menu.append((_('Pause Download'), pause_all))

        if uploadable > 0:
            def restart_all():
                for item in selection:
                    messages.StartUpload(item.id).send_to_backend()
            menu.append((_('Restart Upload'), restart_all))

        return menu

class ItemContextMenuHandlerPlaylist(ItemContextMenuHandler):
    """Context menu handler for playlists."""
    def __init__(self, playlist_id):
        self.playlist_id = playlist_id

    def _remove_context_menu_item(self, selection):
        def do_remove():
            ids = [info.id for info in selection]
            messages.RemoveVideosFromPlaylist(self.playlist_id,
                    ids).send_to_backend()
        return (_('Remove From Playlist'), do_remove)

class ItemContextMenuHandlerPlaylistFolder(ItemContextMenuHandler):
    """Context menu handler for playlist folders."""
    def _remove_context_menu_item(self, selection):
        return None
