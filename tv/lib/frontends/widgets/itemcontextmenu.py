# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""itemcontextmenu.py -- Handle popping up an context menu for an item
"""

from miro import app
from miro import messages
from miro import prefs
from miro import config
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.plat import resources
from miro.plat.frontends.widgets import file_navigator_name
from miro.videoconversion import conversion_manager


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
        # Format for the menu list:
        #
        # Each item is either None or separated into (label, callback),
        # more or less, kinda.  If it's None, it's actually a
        # separator. Otherwise..
        #
        # The label is one of two things:
        #  - A string, which is used as the label for the menu item
        #  - A tuple of (label_text, icon_path), in case you need icons
        #
        # The callback is one of three things:
        #  - None, in which case the menu item is made insensitive
        #  - A list, which means a submenu... should be in the same format
        #    as this normal menu
        #  - A method of some form.  In other words, a *real* callback :)
        if item.downloaded:
            def play_and_stop():
                app.playback_manager.start_with_items([item])

            def play_externally():
                app.widgetapp.open_file(item.video_path)
                messages.MarkItemWatched(item.id).send_to_backend()

            menu = [
                (_('Play'), app.widgetapp.play_selection),
            ]
            if config.get(prefs.PLAY_IN_MIRO):
                menu.append((_('Play Just This Item'), play_and_stop))
                menu.append((_('Play Externally'), play_externally))
            menu.append((_('Add to Playlist'), app.widgetapp.add_to_playlist))
            self._add_remove_context_menu_item(menu, [item])
            menu.append((_("Edit Item"), app.widgetapp.edit_item))
            if item.video_watched:
                menu.append((_('Mark as Unplayed'),
                    messages.MarkItemUnwatched(item.id).send_to_backend))
            else:
                menu.append((_('Mark as Played'),
                    messages.MarkItemWatched(item.id).send_to_backend))
            if item.expiration_date:
                menu.append((_('Keep'),
                    messages.KeepVideo(item.id).send_to_backend))
            if item.seeding_status == 'seeding':
                menu.append((_('Stop Seeding'), messages.StopUpload(item.id).send_to_backend))
            elif item.seeding_status == 'stopped':
                menu.append((_('Resume Seeding'), messages.StartUpload(item.id).send_to_backend))

            menu.append(None)

            convert_menu = self._make_convert_menu()
            menu.append((_('Convert to...'), convert_menu))
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

        view_menu = []
        if not item.is_external:
            view_menu.append((_('Web Page'), lambda: app.widgetapp.open_url(item.permalink)))
        if item.commentslink and item.commentslink != item.permalink:
            view_menu.append((_('Comments'), lambda: app.widgetapp.open_url(item.commentslink)))
        if item.license and item.license != item.permalink:
            view_menu.append((_('License'), lambda: app.widgetapp.open_url(item.license)))
        if item.downloaded:
            if item.file_url != item.permalink and not item.file_url.startswith('file://'):
                view_menu.append((_('File in Browser'), lambda: app.widgetapp.open_url(item.file_url)))
            if file_navigator_name:
                reveal_text = _('File in %(progname)s', {"progname": file_navigator_name})
            else:
                reveal_text = _('File on Disk')
            view_menu.append((reveal_text, lambda: app.widgetapp.check_then_reveal_file(item.video_path)))

        menu.append(None)
        menu.append((_('View'), view_menu))

        if item.has_sharable_url:
            menu.append((_('Share'), lambda: app.widgetapp.share_item(item)))

        return menu

    def _make_context_menu_multiple(self, selection):
        """Make the context menu for multiple items."""
        watched = []
        unwatched = []
        downloaded = []
        downloading = []
        available = []
        paused = []
        uploadable = []
        expiring = []
        for info in selection:
            if info.downloaded:
                downloaded.append(info)
                if info.video_watched:
                    watched.append(info)
                    if info.expiration_date:
                        expiring.append(info)
                else:
                    unwatched.append(info)
            elif info.state == 'paused':
                paused.append(info)
            elif info.state == 'downloading':
                downloading.append(info)
                if (info.download_info.torrent and
                        info.download_info.state != 'uploading'):
                    uploadable.append(info)
            else:
                available.append(info)

        menu = []
        if downloaded:
            menu.append((ngettext('%(count)d Downloaded Item',
                                  '%(count)d Downloaded Items',
                                  len(downloaded),
                                  {"count": len(downloaded)}),
                         None))
            menu.append((_('Play'), app.widgetapp.play_selection)),
            menu.append((_('Add to Playlist'),
                app.widgetapp.add_to_playlist))
            self._add_remove_context_menu_item(menu, selection)
            if watched:
                def mark_unwatched():
                    for item in watched:
                        messages.MarkItemUnwatched(item.id).send_to_backend()
                menu.append((_('Mark as Unplayed'), mark_unwatched))
            if unwatched:
                def mark_watched():
                    for item in unwatched:
                        messages.MarkItemWatched(item.id).send_to_backend()
                menu.append((_('Mark as Played'), mark_watched))
            if expiring:
                def keep_videos():
                    for item in expiring:
                        if item.expiration_date:
                            messages.KeepVideo(item.id).send_to_backend()
                menu.append((_('Keep'), keep_videos))

            menu.append(None)
            convert_menu = self._make_convert_menu()
            menu.append((_('Convert to...'), convert_menu))
            

        if available:
            if len(menu) > 0:
                menu.append(None)
            menu.append((ngettext('%(count)d Available Item',
                                  '%(count)d Available Items',
                                  len(available),
                                  {"count": len(available)}),
                         None))
            def download_all():
                for item in available:
                    messages.StartDownload(item.id).send_to_backend()
            menu.append((_('Download'), download_all))

        if downloading:
            if len(menu) > 0:
                menu.append(None)
            menu.append((ngettext('%(count)d Downloading Item',
                                  '%(count)d Downloading Items',
                                  len(downloading),
                                  {"count": len(downloading)}),
                         None))
            def cancel_all():
                for item in downloading:
                    messages.CancelDownload(item.id).send_to_backend()
            def pause_all():
                for item in downloading:
                    messages.PauseDownload(item.id).send_to_backend()
            menu.append((_('Cancel Download'), cancel_all))
            menu.append((_('Pause Download'), pause_all))

        if paused:
            if len(menu) > 0:
                menu.append(None)
            menu.append((ngettext('%(count)d Paused Item',
                                  '%(count)d Paused Items',
                                  len(paused),
                                  {"count": len(paused)}),
                         None))
            def resume_all():
                for item in paused:
                    messages.ResumeDownload(item.id).send_to_backend()
            menu.append((_('Resume Download'), resume_all))
            def cancel_all():
                for item in paused:
                    messages.CancelDownload(item.id).send_to_backend()
            menu.append((_('Cancel Download'), cancel_all))

        if uploadable:
            def restart_all():
                for item in uploadable:
                    messages.StartUpload(item.id).send_to_backend()
            menu.append((_('Restart Upload'), restart_all))

        return menu
    
    def _make_convert_menu(self):
        convert_menu = []
        sections = conversion_manager.get_converters()
        for index, section in enumerate(sections):
            for converter in section[1]:
                def convert(converter=converter.identifier):
                    app.widgetapp.convert_items(converter)
                convert_menu.append((converter.name, convert))
            if index+1 < len(sections):
                convert_menu.append(None)
        convert_menu.append(None)
        convert_menu.append((_("Show Conversion Folder"),
                             app.widgetapp.reveal_conversions_folder))
        return convert_menu

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
