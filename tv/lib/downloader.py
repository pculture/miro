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

import datetime
import os
import random
import logging
import time

from miro.gtcache import gettext as _
from miro.database import DDBObject, ObjectNotFoundError
from miro.dl_daemon import daemon, command
from miro.download_utils import (next_free_filename, get_file_url_path,
        next_free_directory, filter_directory_name)
from miro.util import (get_torrent_info_hash, returns_unicode, check_u,
                       returns_filename, unicodify, check_f, to_uni, is_magnet_uri)
from miro import app
from miro import dialogs
from miro import displaytext
from miro import eventloop
from miro import httpclient
from miro import models
from miro import prefs
from miro.plat.utils import samefile, unicode_to_filename
from miro import flashscraper
from miro import fileutil
from miro import util
from miro.fileobject import FilenameType

class DownloadStateManager(object):
    """DownloadStateManager: class to store state information about the
    downloader.

    Commands to the downloader is batched and sent every second.  This is
    based on the premise that commands for a particular download id can 
    be completely superceded by a subsequent command, with the exception
    of a pause/resume pair.  For example, a stop command will completely
    supecede a pause command, so if the 2 are sent in quick succession
    only the stop command will be sent by the downloader.  The exception
    to this rule is the pause/resume pair which acts like matter and
    anti-matter, which will nuke itself when they come into contact
    (but dies with not even a whimper instead of a gorgeous display).
    """
    STOP    = command.DownloaderBatchCommand.STOP
    RESUME  = command.DownloaderBatchCommand.RESUME
    PAUSE   = command.DownloaderBatchCommand.PAUSE
    RESTORE = command.DownloaderBatchCommand.RESTORE

    UPDATE_INTERVAL = 1

    def __init__(self):
        self.total_up_rate = 0
        self.total_down_rate = 0
        # a hash of download ids that the server knows about.
        self.downloads = {}
        self.daemon_starter = None
        self.startup_commands = dict()
        self.commands = dict()
        self.bulk_mode = False

    def set_bulk_mode(self):
        self.bulk_mode = True

    def send_initial_updates(self):
        commands = self.startup_commands
        self.startup_commands = None
        if commands:
            c = command.DownloaderBatchCommand(RemoteDownloader.dldaemon,
                                               commands)
            c.send()

    def send_updates(self):
        commands = self.commands
        self.commands = dict()
        if commands:
            c = command.DownloaderBatchCommand(RemoteDownloader.dldaemon,
                                               commands)
            c.send()
        elif self.bulk_mode:
            from miro.messages import DownloaderSyncCommandComplete
            # If we did a pause/resume/cancel all, and there weren't any
            # items in the list to send nobody would re-enable the auto-sort.
            # So we do it here.
            DownloaderSyncCommandComplete().send_to_frontend()
        # Reset the bulk mode notification.
        self.bulk_mode = False
        self.start_updates()

    def start_updates(self):
        eventloop.add_timeout(self.UPDATE_INTERVAL,
                              self.send_updates,
                              "Send Download Command Updates")

    def get_download(self, dlid):
        try:
            return self.downloads[dlid]
        except KeyError:
            return None

    def add_download(self, dlid, downloader):
        self.downloads[dlid] = downloader

    def delete_download(self, dlid):
        try:
            del self.downloads[dlid]
        except KeyError:
            return False
        else:
            return True

    def daemon_started(self):
        return self.daemon_starter and self.daemon_starter.started

    def queue(self, identifier, cmd, args):
        if not self.downloads.has_key(identifier):
            raise ValueError('add_download() not called before queue()')

        # Catch restores first, we will flush them when the downloader's
        # started.
        if cmd == self.RESTORE and not self.daemon_started():
            self.startup_commands[identifier] = (cmd, args)
            return

        exists = self.commands.has_key(identifier)

        # Make sure that a pause/resume pair cancel each other out.  For
        # others, assume that a subsequent command can completely supercede
        # the previous command.
        if exists:
            old_cmd, unused = self.commands[identifier]
            if (old_cmd == self.RESUME and cmd == self.PAUSE or
              old_cmd == self.PAUSE and cmd == self.RESUME):
                # Make sure that we unfreeze it
                self.downloads[identifier].status_updates_frozen = False
                del self.commands[identifier]
                return
            # HACK: When we pause and resume we currently send a download
            # command, then a restore downloader command which doesn't
            # do anything.  This also breaks our general assumption that a 
            # current command can completely supercede any previous queued
            # command so if we see it disable it.  I'm not actually
            # sure why we'd want to send a restore command in this case.
            if cmd == self.RESTORE:
               logging.info('not restoring active download')
               return

        # Freeze the status updates, but don't freeze if it is a restore.
        if not cmd == self.RESTORE:
            self.downloads[identifier].status_updates_frozen = True
        self.commands[identifier] = (cmd, args)

    def init_controller(self):
        """Intializes the download daemon controller.

        This doesn't actually start up the downloader daemon, that's done
        in startup_downloader.  Commands will be queued until then.
        """
        self.daemon_starter = DownloadDaemonStarter()

    def startup_downloader(self):
        """Initialize the downloaders.
    
        This method currently does 2 things.  It deletes any stale files
        self in Incomplete Downloads, then it restarts downloads that have
        been restored from the database.  It must be called before any
        RemoteDownloader objects get created.
        """
        self.daemon_starter.startup()
        # Now that the daemon has started, we can process updates.
        self.send_initial_updates()
        self.start_updates()
    
    def shutdown_downloader(self, callback=None):
        if self.daemon_starter:
            self.daemon_starter.shutdown(callback)
        elif callback:
            callback()

def get_downloader_by_dlid(dlid):
    try:
        return RemoteDownloader.get_by_dlid(dlid)
    except ObjectNotFoundError:
        return None

@returns_unicode
def generate_dlid():
    dlid = u"download%08d" % random.randint(0, 99999999)
    while get_downloader_by_dlid(dlid=dlid):
        dlid = u"download%08d" % random.randint(0, 99999999)
    return dlid

class RemoteDownloader(DDBObject):
    """Download a file using the downloader daemon."""

    # attributes that get set from the BatchUpdateDownloadStatus command
    status_attributes = [
        'state',
        'total_size',
        'current_size',
        'eta',
        'rate',
        'start_time',
        'end_time',
        'short_filename',
        'filename',
        'reason_failed',
        'short_reason_failed',
        'type',
        'retry_time',
        'retry_count',
        'upload_rate',
        'upload_size',
        'activity',
        'seeders',
        'leechers',
        'connections',
        'metainfo',
        'info_hash',
        'filename',
        'eta',
        'rate',
        'upload_rate',
        'activity',
        'seeders',
        'leechers',
        'connections'
    ]
    # default values for attributes in status_attributes
    status_attribute_defaults = {
        'current_size': 0,
        'upload_size': 0,
        'state': u'downloading',
    }
    # status attributes that don't get saved to disk
    temp_status_attributes = [
        'eta',
        'rate',
        'upload_rate',
        'activity',
        'seeders',
        'leechers',
        'connections'
    ]
    # status attributes that we can wait a little while to save to disk
    status_attributes_to_defer = set([
        'current_size',
        'upload_size',
    ])

    def setup_new(self, url, item, content_type=None, channel_name=None):
        check_u(url)
        if content_type:
            check_u(content_type)
        self.orig_url = self.url = url
        self.item_list = []
        self.child_deleted = False
        self.main_item_id = None
        self.dlid = generate_dlid()
        if content_type is None:
            # HACK: Some servers report the wrong content-type for
            # torrent files.  We try to work around that by assuming
            # if the enclosure states that something is a torrent,
            # it's a torrent.  Thanks to j@v2v.cc.
            if item.enclosure_type == u'application/x-bittorrent':
                content_type = item.enclosure_type
        self.content_type = u""
        self.delete_files = True
        self.channel_name = channel_name
        self.manualUpload = False
        self._update_retry_time_dc = None
        self.status_updates_frozen = False
        self.last_update = time.time()
        self.reset_status_attributes()
        if content_type is None:
            self.content_type = u""
        else:
            self.content_type = content_type

        if self.content_type == u'':
            self.get_content_type()
        else:
            self.run_downloader()

    def setup_restored(self):
        self.status_updates_frozen = False
        self.last_update = time.time()
        self._update_retry_time_dc = None
        self.delete_files = True
        self.item_list = []
        if self.dlid == 'noid':
            # this won't happen nowadays, but it can for old databases
            self.dlid = generate_dlid()

    def reset_status_attributes(self):
        """Reset the attributes that track downloading info."""
        for attr_name in self.status_attributes:
            default = self.status_attribute_defaults.get(attr_name)
            setattr(self, attr_name, default)

    def update_status_attributes(self, status_dict):
        """Reset the attributes that track downloading info."""
        for attr_name in self.status_attributes:
            if attr_name in status_dict:
                value = status_dict[attr_name]
            else:
                value = self.status_attribute_defaults.get(attr_name)
            # only set attributes if something's changed.  This makes our
            # UPDATE statments contain less data
            if getattr(self, attr_name) != value:
                setattr(self, attr_name, value)

    def get_status_for_downloader(self):
        status = dict((name, getattr(self, name))
                     for name in self.status_attributes)
        # status_attributes only tracks the attributes that we update based on
        # the downloader status updates.  Also add values for that we send to
        # the downloader, but that don't change from status updates.
        status['channel_name'] = self.channel_name
        status['dlid'] = self.dlid
        status['url'] = self.url
        return status

    @classmethod
    def finished_view(cls):
        return cls.make_view("state in ('finished', 'uploading', "
                             "'uploading-paused')")

    @classmethod
    def auto_uploader_view(cls):
        return cls.make_view("state == 'uploading' AND NOT manualUpload")

    @classmethod
    def get_by_dlid(cls, dlid):
        return cls.make_view('dlid=?', (dlid,)).get_singleton()

    @classmethod
    def get_by_url(cls, url):
        return cls.make_view('orig_url=?', (url,)).get_singleton()

    @classmethod
    def orphaned_view(cls):
        """Downloaders with no items associated with them."""
        return cls.make_view('id NOT IN (SELECT downloader_id from item)')

    def signal_change(self, needs_save=True, needs_signal_item=True):
        DDBObject.signal_change(self, needs_save=needs_save)
        if needs_signal_item:
            for item in self.item_list:
                item.download_stats_changed()

    def on_content_type(self, info):
        if not self.id_exists():
            return

        if info['status'] == 200:
            self.url = info['updated-url'].decode('ascii','replace')
            self.content_type = None
            try:
                self.content_type = info['content-type'].decode('ascii',
                                                                'replace')
            except (KeyError, UnicodeDecodeError):
                self.content_type = None
            self.run_downloader()
        else:
            error = httpclient.UnexpectedStatusCode(info['status'])
            self.on_content_type_error(error)

    def on_content_type_error(self, error):
        if not self.id_exists():
            return

        if isinstance(error, httpclient.AuthorizationCanceled):
            # user canceled out of the authorization request, so stop the
            # download.
            self.state = u'stopped'
            self.signal_change()
            return

        # we can't get a content type.  it's possible that this is a
        # retryable error so we're going to set the content_type to
        # None and run the downloader.  it'll handle HTTP errors
        # better than we will.
        self.content_type = None
        self.run_downloader()

    def get_content_type(self):
        if is_magnet_uri(self.url):
            self.content_type = u'application/x-magnet'
            return 
        httpclient.grab_headers(self.url, self.on_content_type,
                                self.on_content_type_error)

    @classmethod
    def initialize_daemon(cls):
        RemoteDownloader.dldaemon = daemon.ControllerDaemon()

    def _get_rates(self):
        state = self.get_state()
        if state == u'downloading':
            return self.rate, self.upload_rate
        if state == u'uploading':
            return (0, self.upload_rate)
        return (0, 0)

    def before_changing_rates(self):
        rates = self._get_rates()
        if rates[0] is not None:
            app.download_state_manager.total_down_rate -= rates[0]
        if rates[1] is not None:
            app.download_state_manager.total_up_rate -= rates[1]

    def after_changing_rates(self):
        rates = self._get_rates()
        if rates[0] is not None:
            app.download_state_manager.total_down_rate += rates[0]
        if rates[1] is not None:
            app.download_state_manager.total_up_rate += rates[1]

    @classmethod
    def update_status(cls, data, cmd_done=False):
        for field in data:
            if field not in ['filename', 'short_filename', 'metainfo']:
                data[field] = unicodify(data[field])

        self = get_downloader_by_dlid(dlid=data['dlid'])
        # FIXME: how do we get all of the possible bit torrent
        # activity strings into gettext? --NN
        if data.has_key('activity') and data['activity']:
            data['activity'] = _(data['activity'])

        if self is not None:
            now = time.time()
            last_update = self.last_update
            state = self.get_state()
            new_state = data.get('state', u'downloading')

            # If this item was marked as pending update, then any update
            # which comes in now which does not have cmd_done set is void.
            if not cmd_done and self.status_updates_frozen:
                logging.debug('self = %s, '
                              'saved state = %s '
                              'downloader state = %s.  '
                              'Discard.',
                              self, state, new_state)
                # treat as stale
                return False

            # If the state is one which we set and was meant to be passed
            # through to the downloader (valid_states), and the downloader
            # replied with something that was a response to a previous
            # download command, and state was also a part of valid_states,
            # but the saved state and the new state do not match
            # then it means the message is stale.
            #
            # Have a think about why this is true: when you set a state,
            # which is authoritative, to the downloader you expect it
            # to reply with that same state.  If they do not match then it
            # means the message is stale.
            #
            # The exception to this rule is if the downloader replies with
            # an error state, or if downloading has transitioned to finished
            # state.
            #
            # This also does not apply to any state which we set on the
            # downloader via a restore command.  A restore command before
            # a pause/resume/cancel will work as intended, and no special
            # trickery is required.  A restore command which happens after
            # a pause/resume/cancel is void, so no work is required.
            #
            # I hope this makes sense and is clear!
            valid_states = (u'downloading', u'paused', u'stopped',
                            u'uploading-paused', u'finished')
            if (cmd_done and
              state in valid_states and new_state in valid_states and
              state != new_state):
                if not (state == u'downloading' and new_state == u'finished'):
                    logging.debug('self = %s STALE.  '
                                  'Saved state %s, got state %s.  Discarding.',
                                  self, state, new_state)
                    return False

            # We are updating!  Reset the status_updates_frozen flag.
            self.status_updates_frozen = False

            # We have something to update: update the last updated timestamp.
            self.last_update = now

            was_finished = self.is_finished()
            old_filename = self.get_filename()

            self.before_changing_rates()
            self.update_status_attributes(data)
            self.after_changing_rates()

            # Store the time the download finished
            finished = self.is_finished() and not was_finished
            name_changed = self.get_filename() != old_filename
            file_migrated = (self.is_finished() and name_changed)

            if ((self.get_state() == u'uploading'
                 and not self.manualUpload
                 and (app.config.get(prefs.LIMIT_UPLOAD_RATIO)
                      and self.get_upload_ratio() > app.config.get(prefs.UPLOAD_RATIO)))):
                self.stop_upload()

            self.signal_change()

            if finished:
                for item in self.item_list:
                    item.on_download_finished()
            elif file_migrated:
                self._file_migrated(old_filename)
            elif name_changed and old_filename and self.metainfo is not None:
                # update the torren title; happens with magnet URLs since we
                # don't have a real one when the download starts.  The
                # old_filename check is to prevent things with existing titles
                # from being renamed (#18656).
                new_title = util.get_name_from_torrent_metadata(self.metainfo)
                for item in self.item_list:
                    if item.torrent_title is None:
                        item.torrent_title = new_title
                        item.signal_change()
        return True

    def run_downloader(self):
        """This is the actual download thread.
        """
        flashscraper.try_scraping_url(self.url, self._run_downloader)

    def _run_downloader(self, url, content_type=None, title=None):
        if not self.id_exists():
            # we got deleted while we were doing the flash scraping
            return
        if content_type is not None:
            self.content_type = content_type
        if url is not None:
            if title is not None:
                for mem in self.item_list:
                    if not mem.title:
                        mem.title = title

            self.url = url
            logging.debug("downloading url %s", self.url)
            args = dict(url=self.url, content_type=self.content_type,
                        channel_name=self.channel_name)
            app.download_state_manager.add_download(self.dlid, self)
            app.download_state_manager.queue(self.dlid,
                                             app.download_state_manager.RESUME,
                                             args)
            self.state = u'downloading'
        else:
            self.state = u'failed'
            self.short_reason_failed = _('File not found')
            self.reason_failed = _('Flash URL Scraping Error')
        self.signal_change()

    def pause(self):
        """Pauses the download."""
        if app.download_state_manager.get_download(self.dlid):
            args = dict(upload=False)
            app.download_state_manager.queue(self.dlid,
                                             app.download_state_manager.PAUSE,
                                             args)
        self.state = u'paused'
        self.signal_change()

    def stop(self, delete):
        """Stops the download and removes the partially downloaded
        file.
        """
        if self.get_state() in [u'downloading', u'uploading', u'paused',
                                u'offline']:
            if app.download_state_manager.get_download(self.dlid):
                args = dict(upload=False, delete=delete)
                app.download_state_manager.queue(
                    self.dlid,
                    app.download_state_manager.STOP,
                    args)
                app.download_state_manager.delete_download(self.dlid)

        if delete:
            self.delete()
        self.state = u'stopped'
        self.signal_change()

    def delete(self):
        if self.filename is None:
            return
        try:
            fileutil.delete(self.filename)
        except OSError:
            logging.exception("Error deleting downloaded file: %s",
                              to_uni(self.filename))

        parent = os.path.join(fileutil.expand_filename(self.filename),
                              os.path.pardir)
        parent = os.path.normpath(parent)
        movies_dir = fileutil.expand_filename(app.config.get(prefs.MOVIES_DIRECTORY))
        if ((os.path.exists(parent) and os.path.exists(movies_dir)
             and not samefile(parent, movies_dir)
             and len(os.listdir(parent)) == 0)):
            try:
                os.rmdir(parent)
            except OSError:
                logging.exception("Error deleting empty download directory: %s",
                                  to_uni(parent))
        self.filename = None

    def start(self):
        """Continues a paused, stopped, or failed download thread
        """
        if self.get_state() == u'failed':
            # For failed downloads, don't trust the redirected URL (#14232)
            self.url = self.orig_url
            app.download_state_manager.delete_download(self.dlid)
            self.dlid = generate_dlid()
            self.before_changing_rates()
            self.reset_status_attributes()
            self.after_changing_rates()
            if self.content_type == u"":
                self.get_content_type()
            else:
                self.run_downloader()
            self.signal_change()
        elif self.get_state() in (u'stopped', u'paused', u'offline'):
            if app.download_state_manager.get_download(self.dlid):
                args = dict(url=self.url, content_type=self.content_type,
                            channel_name=self.channel_name)
                app.download_state_manager.queue(
                    self.dlid,
                    app.download_state_manager.RESUME,
                    args)
            self.state = u'downloading'
            self.restart()
            self.signal_change()

    def migrate(self, directory):
        if app.download_state_manager.get_download(self.dlid):
            c = command.MigrateDownloadCommand(RemoteDownloader.dldaemon,
                                               self.dlid, directory)
            c.send()
        else:
            # downloader doesn't have our dlid.  Move the file ourself.
            short_filename = self.short_filename
            if not short_filename:
                logging.warning(
                    "can't migrate download; no shortfilename!  URL was %s",
                    self.url)
                return
            filename = self.filename
            if not filename:
                logging.warning(
                    "can't migrate download; no filename!  URL was %s",
                    self.url)
                return
            if fileutil.exists(filename):
                if self.channel_name is not None:
                    channel_name = filter_directory_name(self.channel_name)
                    directory = os.path.join(directory, channel_name)
                if not os.path.exists(directory):
                    try:
                        fileutil.makedirs(directory)
                    except OSError:
                        # FIXME - what about permission issues?
                        pass
                newfilename = os.path.join(directory, short_filename)
                if newfilename == filename:
                    return
                # create a file or directory to serve as a placeholder before
                # we start to migrate.  This helps ensure that the destination
                # we're migrating too is not already taken.
                try:
                    is_dir = fileutil.isdir(filename)
                    if is_dir:
                        newfilename = next_free_directory(newfilename)
                        fp = None
                    else:
                        newfilename, fp = next_free_filename(newfilename)
                        fp.close()
                except ValueError:
                    func = ('next_free_directory' if is_dir
                            else 'next_free_filename')
                    logging.warn('migrate: %s failed.  candidate = %r',
                                 func, newfilename)
                else:
                    def callback():
                        self.filename = newfilename
                        self.signal_change(needs_signal_item=False)
                        self._file_migrated(filename)
                    fileutil.migrate_file(filename, newfilename, callback)
        for i in self.item_list:
            i.migrate_children(directory)

    def _file_migrated(self, old_filename):
        # Make sure that item_list is populated with items, see (#12202)
        for item in models.Item.downloader_view(self.id):
            self.add_item(item)
        for item in self.item_list:
            item.on_downloader_migrated(old_filename, self.get_filename())

    def set_delete_files(self, delete_files):
        self.delete_files = delete_files

    def set_channel_name(self, channel_name):
        if self.channel_name is None:
            if channel_name:
                check_f(channel_name)
            self.channel_name = channel_name

    def remove(self):
        """Removes downloader from the database and deletes the file.
        """
        rates = self._get_rates()
        if rates[0] is not None:
            app.download_state_manager.total_down_rate -= rates[0]
        if rates[1] is not None:
            app.download_state_manager.total_up_rate -= rates[1]
        if self.is_finished():
            app.local_metadata_manager.remove_file(self.get_filename())
        self.stop(self.delete_files)
        DDBObject.remove(self)

    def get_type(self):
        """Get the type of download.  Will return either "http" or
        "bittorrent".
        """
        self.confirm_db_thread()
        if ((self.content_type == u'application/x-bittorrent'
             or self.content_type == u'application/x-magnet')):
            return u"bittorrent"

        return u"http"

    def add_item(self, item):
        """In case multiple downloaders are getting the same file, we
        can support multiple items
        """
        if item not in self.item_list:
            self.item_list.append(item)
            if self.main_item_id is None:
                self.main_item_id = item.id
                self.signal_change()

    def remove_item(self, item):
        self.item_list.remove(item)
        if len (self.item_list) == 0:
            self.remove()
        elif item.id == self.main_item_id:
            self.main_item_id = self.item_list[0].id
            self.signal_change()

    def get_rate(self):
        self.confirm_db_thread()
        return self.rate

    def get_eta(self):
        self.confirm_db_thread()
        return self.eta

    @returns_unicode
    def get_startup_activity(self):
        self.confirm_db_thread()
        activity = self.activity
        if (activity is None and self.retry_count is not None and
             self.retry_time is not None):
            activity = self._calc_retry_time()
            if self._update_retry_time_dc is None:
                self._update_retry_time_dc = eventloop.add_timeout(1,
                        self._update_retry_time, 'Updating retry time')
        if activity is None:
            return _("starting up")
        return activity

    def _calc_retry_time(self):
        if self.retry_time > datetime.datetime.now():
            retry_delta = self.retry_time - datetime.datetime.now()
            time_str = displaytext.time_string(retry_delta.seconds)
            return _('no connection - retrying in %(time)s', {"time": time_str})
        else:
            return _('no connection - retrying soon')

    def _update_retry_time(self):
        if self.id_exists():
            # calling signal_change() will cause the us to call
            # get_startup_activity() again which will have a new time now.
            self.signal_change(needs_save=False)
            self._update_retry_time_dc = None

    def _cancel_retry_time_update(self):
        if self._update_retry_time_dc:
            self._update_retry_time_dc.cancel()
            self._update_retry_time_dc = None

    @returns_unicode
    def get_reason_failed(self):
        """Returns the reason for the failure of this download.  This
        should only be called when the download is in the failed
        state.
        """
        if not self.get_state() == u'failed':
            msg = u"get_reason_failed() called on a non-failed downloader"
            raise ValueError(msg)
        self.confirm_db_thread()
        if self.reason_failed is not None:
            return self.reason_failed
        else:
            return _("Unknown")

    @returns_unicode
    def get_short_reason_failed(self):
        if not self.get_state() == u'failed':
            msg = u"get_short_reason_failed() called on a non-failed downloader"
            raise ValueError(msg)
        self.confirm_db_thread()
        if self.short_reason_failed is not None:
            return self.short_reason_failed
        else:
            return _("Unknown")

    @returns_unicode
    def get_url(self):
        """Returns the URL we're downloading
        """
        self.confirm_db_thread()
        return self.url

    @returns_unicode
    def get_state(self):
        """Returns the state of the download: downloading, paused,
        uploading, uploading-paused, stopped, failed, or finished.
        """
        self.confirm_db_thread()
        return self.state

    def is_finished(self):
        return self.get_state() in (u'finished', u'uploading',
                                    u'uploading-paused')

    def get_total_size(self):
        """Returns the total size of the download in bytes.
        """
        self.confirm_db_thread()
        return self.total_size

    def get_current_size(self):
        """Returns the current amount downloaded in bytes.
        """
        self.confirm_db_thread()
        return self.current_size

    @returns_filename
    def get_filename(self):
        """Returns the filename that we're downloading to.  Should not be
        called until state is "finished."
        """
        self.confirm_db_thread()
        return self.filename

    def get_upload_ratio(self):
        size = self.get_current_size()
        if size == 0:
            return 0
        return self.upload_size / size

    def restart_on_startup_if_needed(self):
        if not self.id_exists():
            return
        if app.download_state_manager.get_download(self.dlid):
            # something has caused us to restart already, (for
            # example, the user selects "resume seeding").  squelch
            # any automatic behaviour (#12462)
            return
        if self.get_state() in (u'downloading', u'offline'):
            self.restart()
        if self.get_state() == u'uploading':
            if ((self.manualUpload
                 or (app.config.get(prefs.LIMIT_UPLOAD_RATIO)
                     and self.get_upload_ratio() < app.config.get(prefs.UPLOAD_RATIO)))):
                self.restart()
            else:
                self.stop_upload()

    def restart(self):
        if self.type is None:
            if self.content_type == u"":
                self.get_content_type()
            else:
                self.run_downloader()
        else:
            app.download_state_manager.add_download(self.dlid, self)
            self.state = u'downloading'
            args = dict(downloader=self.get_status_for_downloader())
            app.download_state_manager.queue(
                self.dlid,
                app.download_state_manager.RESTORE,
                args)

    def start_upload(self):
        """
        Start an upload (seeding).
        """
        if self.get_type() != u'bittorrent':
            logging.warn("called start_upload for non-bittorrent downloader")
            return
        if self.child_deleted:
            title = "Can't Resume Seeding"
            msg = ("Seeding cannot resume because part of this torrent "
                   "has been deleted.")
            dialogs.MessageBoxDialog(title, msg).run()
            return
        if self.get_state() not in (u'finished', u'uploading-paused'):
            logging.warn("called start_upload when downloader state is: %s",
                         self.get_state())
            return
        self.manualUpload = True
        if app.download_state_manager.get_download(self.dlid):
            args = dict(url=self.url, content_type=self.content_type,
                        channel_name=self.channel_name)
            app.download_state_manager.queue(self.dlid,
                                             app.download_state_manager.RESUME,
                                             args)
        else:
            self.before_changing_rates()
            self.state = u'uploading'
            self.after_changing_rates()
            self.restart()
            self.signal_change()

    def stop_upload(self):
        """
        Stop uploading/seeding and set status as "finished".
        """
        if app.download_state_manager.get_download(self.dlid):
            args = dict(upload=True)
            app.download_state_manager.queue(self.dlid,
                app.download_state_manager.STOP, args)
            app.download_state_manager.delete_download(self.dlid)
        self.before_changing_rates()
        self.state = u'finished'
        self.after_changing_rates()
        self.signal_change()

    def pause_upload(self):
        """
        Stop uploading/seeding and set status as "uploading-paused".
        """
        if app.download_state_manager.get_download(self.dlid):
            args = dict(upload=True)
            app.download_state_manager.queue(self.dlid,
                app.download_state_manager.PAUSE,
                args)
            app.download_state_manager.delete_download(self.dlid)
        self.before_changing_rates()
        self.state = u"uploading-paused"
        self.after_changing_rates()
        self.signal_change()

def cleanup_incomplete_downloads():
    download_dir = os.path.join(app.config.get(prefs.MOVIES_DIRECTORY),
                                'Incomplete Downloads')
    if not fileutil.exists(download_dir):
        return

    files_in_use = set()
    for downloader in RemoteDownloader.make_view():
        if downloader.get_state() in ('downloading', 'paused',
                                     'offline', 'uploading', 'finished',
                                     'uploading-paused'):
            filename = downloader.get_filename()
            if filename:
                if not fileutil.isabs(filename):
                    filename = os.path.join(download_dir, filename)
                files_in_use.add(filename)

    try:
        entries = fileutil.listdir(download_dir)
    except OSError:
        entries = []

    for f in entries:
        f = os.path.join(download_dir, f)
        if f not in files_in_use:
            try:
                if fileutil.isfile(f):
                    fileutil.remove(f)
                elif fileutil.isdir(f):
                    fileutil.rmtree(f)
            except OSError:
                # FIXME - maybe a permissions error?
                pass

def kill_uploaders(*args):
    torrent_limit = app.config.get(prefs.UPSTREAM_TORRENT_LIMIT)
    auto_uploads = list(RemoteDownloader.auto_uploader_view())
    for dler in auto_uploads[torrent_limit:]:
        dler.stop_upload()

def _on_config_change(obj, key, value):
    if key == prefs.UPSTREAM_TORRENT_LIMIT.key:
        kill_uploaders()


class DownloadDaemonStarter(object):
    def __init__(self):
        RemoteDownloader.initialize_daemon()
        self.downloads_at_startup = list(RemoteDownloader.make_view())
        self.started = False
        self._config_callback_handle = None
        self._download_tracker = None

    def limit_uploaders(self):
        view = RemoteDownloader.auto_uploader_view()
        self._download_tracker = view.make_tracker()
        self._download_tracker.connect('added', kill_uploaders)
        self._config_callback_handle = app.backend_config_watcher.connect(
                "changed", _on_config_change)
        kill_uploaders()

    def disconnect_signals(self):
        if self._download_tracker is not None:
            self._download_tracker.unlink()
            self._download_tracker = None
        if self._config_callback_handle is not None:
            app.backend_config_watcher.disconnect(self._config_callback_handle)
            self._config_callback_handle = None

    def startup(self):
        cleanup_incomplete_downloads()
        RemoteDownloader.dldaemon.start_downloader_daemon()
        self.limit_uploaders()
        self.restart_downloads()
        self.started = True

    def restart_downloads(self):
        for downloader in self.downloads_at_startup:
            downloader.restart_on_startup_if_needed()

    def shutdown(self, callback):
        self.disconnect_signals()
        self.shutdown_callback = callback
        if not self.started:
            self._on_shutdown()
        else:
            RemoteDownloader.dldaemon.shutdown_downloader_daemon(
                    callback=self._on_shutdown)

    def _on_shutdown(self):
        shutdown_downloader_objects()
        self.shutdown_callback()
        del self.shutdown_callback

def lookup_downloader(url):
    try:
        return RemoteDownloader.get_by_url(url)
    except ObjectNotFoundError:
        return None

def get_existing_downloader_by_url(url):
    downloader = lookup_downloader(url)
    return downloader

def get_existing_downloader(item):
    try:
        return RemoteDownloader.get_by_id(item.downloader_id)
    except ObjectNotFoundError:
        return None

def get_downloader_for_item(item):
    existing = get_existing_downloader(item)
    if existing:
        return existing
    url = item.get_url()
    existing = get_existing_downloader_by_url(url)
    if existing:
        return existing
    channel_name = unicode_to_filename(item.get_channel_title(True))
    if not channel_name:
        channel_name = None
    if url.startswith(u'file://'):
        path = get_file_url_path(url)
        try:
            get_torrent_info_hash(path)
        except ValueError:
            raise ValueError("Don't know how to handle %s" % url)
        except (OSError, IOError):
            return None
        else:
            return RemoteDownloader(url, item, u'application/x-bittorrent',
                                    channel_name=channel_name)
    elif is_magnet_uri(url):
        return RemoteDownloader(url, item, u'application/x-magnet')
    else:
        return RemoteDownloader(url, item, channel_name=channel_name)

def shutdown_downloader_objects():
    """Perform shutdown code for RemoteDownloaders.

    This means a couple things:
      - Make sure any RemoteDownloaders with pending changes get saved.
      - Cancel the update retry time callbacks
    """
    for downloader in RemoteDownloader.make_view():
        downloader._cancel_retry_time_update()

def reset_download_stats():
    """Set columns in the remote_downloader table to None if they track
    temporary data, like eta or rate.
    """
    # FIXME: it's a little weird to be using app.db's cursor here
    setters = ['%s=NULL' % name
               for name in RemoteDownloader.temp_status_attributes
              ]
    app.db.cursor.execute("UPDATE remote_downloader SET %s" %
                          ', '.join(setters))
    app.db.connection.commit()


