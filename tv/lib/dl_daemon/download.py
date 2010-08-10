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

import os
import re
import stat
from threading import RLock
from copy import copy
import sys
import datetime
import logging

from miro.gtcache import gettext as _

import libtorrent as lt
from miro.clock import clock
from miro.download_utils import (
    clean_filename, next_free_filename, check_filename_extension,
    filter_directory_name, filename_from_url, get_file_url_path)
from miro import eventloop
from miro import httpclient
from miro import fileutil

from miro import config
from miro import prefs

from miro.dl_daemon import command, daemon
from miro.util import check_f, check_u, stringify, MAX_TORRENT_SIZE
from miro.plat.utils import get_available_bytes_for_movies, utf8_to_filename

chatter = True

# a hash of download ids to downloaders
_downloads = {}

_lock = RLock()

def config_received():
    TORRENT_SESSION.startup()

def create_downloader(url, contentType, dlid):
    check_u(url)
    check_u(contentType)
    if contentType == u'application/x-bittorrent':
        return BTDownloader(url, dlid)
    else:
        return HTTPDownloader(url, dlid, expectedContentType=contentType)

def start_new_download(url, dlid, contentType, channelName):
    """Creates a new downloader object.

    Returns id on success, None on failure.
    """
    check_u(url)
    check_u(contentType)
    if channelName:
        check_f(channelName)
    dl = create_downloader(url, contentType, dlid)
    dl.channelName = channelName
    _downloads[dlid] = dl

def pause_download(dlid):
    try:
        download = _downloads[dlid]
    except KeyError:
        # There is no download with this id
        return True
    return download.pause()

def info_hash_to_long(info_hash):
    """The info_hash() method from libtorrent returns a "big_number" object.
    This doesn't hash very well: different instances with the same value
    will have different hashes.  So we need to convert them to long objects,
    though this weird process.
    """
    return long(str(info_hash), 16)

def start_download(dlid):
    try:
        download = _downloads[dlid]
    except KeyError:
        # There is no download with this id
        err = u"in start_download(): no downloader with id %s" % dlid
        c = command.DownloaderErrorCommand(daemon.LAST_DAEMON, err)
        c.send()
        return True
    return download.start()

def stop_download(dlid, delete):
    _lock.acquire()
    try:
        download = _downloads[dlid]
        del _downloads[dlid]
    except KeyError:
        # There is no download with this id
        return True
    finally:
        _lock.release()

    return download.stop(delete)

def stop_upload(dlid):
    _lock.acquire()
    try:
        download = _downloads[dlid]
        if download.state not in (u"uploading", u"uploading-paused"):
            return
        del _downloads[dlid]
    except KeyError:
        # There is no download with this id
        return
    finally:
        _lock.release()
    return download.stop_upload()

def pause_upload(dlid):
    _lock.acquire()
    try:
        download = _downloads[dlid]
        if download.state != u"uploading":
            return
        del _downloads[dlid]
    except KeyError:
        # There is no download with this id
        return
    finally:
        _lock.release()
    return download.pause_upload()

def migrate_download(dlid, directory):
    check_f(directory)
    try:
        download = _downloads[dlid]
    except KeyError:
        # There is no download with this id
        return

    if download.state in (u"finished", u"uploading", u"uploading-paused"):
        download.move_to_directory(directory)

def get_download_status(dlids=None):
    statuses = {}
    for key in _downloads.keys():
        if dlids is None or dlids == key or key in dlids:
            try:
                statuses[key] = _downloads[key].get_status()
            except KeyError:
                pass
    return statuses

def shutdown():
    logging.info("Shutting down downloaders...")
    for dlid in _downloads:
        _downloads[dlid].shutdown()
    logging.info("Shutting down torrent session...")
    TORRENT_SESSION.shutdown()

def restore_downloader(downloader):
    if downloader['dlid'] in _downloads:
        logging.warn("Not restarting active downloader: %s",
                downloader['dlid'])
        return

    downloader = copy(downloader)
    dler_type = downloader.get('dlerType')
    if dler_type == u'HTTP':
        dl = HTTPDownloader(restore=downloader)
    elif dler_type == u'BitTorrent':
        dl = BTDownloader(restore=downloader)
    else:
        err = u"in restore_downloader(): unknown dlerType: %s" % dler_type
        c = command.DownloaderErrorCommand(daemon.LAST_DAEMON, err)
        c.send()
        return

    _downloads[downloader['dlid']] = dl

class TorrentSession(object):
    """Contains the bittorrent session and handles updating all
    running bittorrents.
    """
    def __init__(self):
        self.torrents = set()
        self.info_hash_to_downloader = {}
        self.session = None
        self.pnp_on = None
        self.pe_set = None
        self.enc_req = None

    def startup(self):
        fingerprint = lt.fingerprint("MR", 1, 1, 0, 0)
        self.session = lt.session(fingerprint)
        self.listen()
        self.set_upnp()
        self.set_upload_limit()
        self.set_download_limit()
        self.set_encryption()
        config.add_change_callback(self.config_changed)

    def listen(self):
        self.session.listen_on(config.get(prefs.BT_MIN_PORT),
                               config.get(prefs.BT_MAX_PORT))

    def set_upnp(self):
        use_upnp = config.get(prefs.USE_UPNP)
        if use_upnp == self.pnp_on:
            return
        self.pnp_on = use_upnp
        if use_upnp:
            self.session.start_upnp()
        else:
            self.session.stop_upnp()

    def set_upload_limit(self):
        limit = -1
        if config.get(prefs.LIMIT_UPSTREAM):
            limit = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
            limit = limit * (2 ** 10)
            if limit > sys.maxint:
                # avoid OverflowErrors by keeping the value an integer
                limit = sys.maxint
        self.session.set_upload_rate_limit(limit)

    def set_download_limit(self):
        limit = -1
        if config.get(prefs.LIMIT_DOWNSTREAM_BT):
            limit = config.get(prefs.DOWNSTREAM_BT_LIMIT_IN_KBS)
            limit = limit * (2 ** 10)
            if limit > sys.maxint:
                # avoid OverflowErrors by keeping the value an integer
                limit = sys.maxint
        self.session.set_download_rate_limit(limit)

    def set_connection_limit(self):
        limit = -1
        if config.get(prefs.LIMIT_CONNECTIONS_BT):
            limit = config.get(prefs.CONNECTION_LIMIT_BT_NUM)
            if limit > 65536:
                # there are only 2**16 TCP port numbers
                limit = 65536
        self.session.set_max_connections(limit)

    def set_encryption(self):
        if self.pe_set is None:
            self.pe_set = lt.pe_settings()
        enc_req = config.get(prefs.BT_ENC_REQ)
        if enc_req != self.enc_req:
            self.enc_req = enc_req
            if enc_req:
                self.pe_set.in_enc_policy = lt.enc_policy.forced
                self.pe_set.out_enc_policy = lt.enc_policy.forced
            else:
                self.pe_set.in_enc_policy = lt.enc_policy.enabled
                self.pe_set.out_enc_policy = lt.enc_policy.enabled
            self.session.set_pe_settings(self.pe_set)

    def shutdown(self):
        config.remove_change_callback(self.config_changed)

    def config_changed(self, key, value):
        if key == prefs.BT_MIN_PORT.key:
            if value > self.session.listen_port():
                self.listen()
        elif key == prefs.BT_MAX_PORT.key:
            if value < self.session.listen_port():
                self.listen()
        elif key == prefs.USE_UPNP.key:
            self.set_upnp()
        elif key in (prefs.LIMIT_UPSTREAM.key,
                     prefs.UPSTREAM_LIMIT_IN_KBS.key):
            self.set_upload_limit()
        elif key in (prefs.LIMIT_DOWNSTREAM_BT.key,
                     prefs.DOWNSTREAM_BT_LIMIT_IN_KBS.key):
            self.set_download_limit()
        elif key == prefs.BT_ENC_REQ.key:
            self.set_encryption()
        elif key in (prefs.LIMIT_CONNECTIONS_BT.key,
                     prefs.CONNECTION_LIMIT_BT_NUM.key):
            self.set_connection_limit()

    def find_duplicate_torrent(self, torrent_info):
        info_hash = info_hash_to_long(torrent_info.info_hash())
        return self.info_hash_to_downloader.get(info_hash)

    def add_torrent(self, downloader):
        self.torrents.add(downloader)
        info_hash = info_hash_to_long(downloader.torrent.info_hash())
        self.info_hash_to_downloader[info_hash] = downloader

    def remove_torrent(self, downloader):
        if downloader in self.torrents:
            self.torrents.remove(downloader)
            info_hash = info_hash_to_long(downloader.torrent.info_hash())
            del self.info_hash_to_downloader[info_hash]

    def update_torrents(self):
        # Copy this set into a list in case any of the torrents gets
        # removed during the iteration.
        for torrent in [x for x in self.torrents]:
            torrent.update_status()

TORRENT_SESSION = TorrentSession()

class DownloadStatusUpdater(object):
    """Handles updating status for all in progress downloaders.

    On OS X and gtk if the user is on the downloads page and has a
    bunch of downloads going, this can be a fairly CPU intensive task.
    DownloadStatusUpdaters mitigate this in 2 ways.

    1. DownloadStatusUpdater objects batch all status updates into one
       big update which takes much less CPU.

    2. The update don't happen fairly infrequently (currently every 5
       seconds).

    Because updates happen infrequently, DownloadStatusUpdaters should
    only be used for progress updates, not events like downloads
    starting/finishing.  For those just call update_client() since they
    are more urgent, and don't happen often enough to cause CPU
    problems.
    """

    UPDATE_CLIENT_INTERVAL = 1

    def __init__(self):
        self.to_update = set()

    def start_updates(self):
        eventloop.add_timeout(self.UPDATE_CLIENT_INTERVAL, self.do_update,
                "Download status update")

    def do_update(self):
        try:
            TORRENT_SESSION.update_torrents()
            statuses = []
            for downloader in self.to_update:
                statuses.append(downloader.get_status())
            self.to_update = set()
            if statuses:
                command.BatchUpdateDownloadStatus(daemon.LAST_DAEMON,
                        statuses).send()
        finally:
            eventloop.add_timeout(self.UPDATE_CLIENT_INTERVAL, self.do_update,
                    "Download status update")

    def queue_update(self, downloader):
        self.to_update.add(downloader)

DOWNLOAD_UPDATER = DownloadStatusUpdater()

RETRY_TIMES = (
    60,
    5 * 60,
    10 * 60,
    30 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    24 * 60 * 60
    )

class BGDownloader(object):
    def __init__(self, url, dlid):
        self.dlid = dlid
        self.url = url
        self.startTime = clock()
        self.endTime = self.startTime
        self.shortFilename = filename_from_url(url)
        self.pick_initial_filename()
        self.state = u"downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.shortReasonFailed = self.reasonFailed = u"No Error"
        self.retryTime = None
        self.retryCount = -1

    def get_url(self):
        return self.url

    def get_status(self):
        return {'dlid': self.dlid,
            'url': self.url,
            'state': self.state,
            'totalSize': self.totalSize,
            'currentSize': self.currentSize,
            'eta': self.get_eta(),
            'rate': self.get_rate(),
            'uploaded': 0,
            'filename': self.filename,
            'startTime': self.startTime,
            'endTime': self.endTime,
            'shortFilename': self.shortFilename,
            'reasonFailed': self.reasonFailed,
            'shortReasonFailed': self.shortReasonFailed,
            'dlerType': None,
            'retryTime': self.retryTime,
            'retryCount': self.retryCount,
            'channelName': self.channelName}

    def update_client(self):
        x = command.UpdateDownloadStatus(daemon.LAST_DAEMON, self.get_status())
        return x.send()

    def pick_initial_filename(self, suffix=".part", torrent=False):
        """Pick a path to download to based on self.shortFilename.

        This method sets self.filename, as well as creates any leading
        paths needed to start downloading there.

        If the torrent flag is true, then the filename we're working
        with is utf-8 and shouldn't be transformed in any way.

        If the torrent flag is false, then the filename we're working
        with is ascii and needs to be transformed into something sane.
        (default)
        """
        download_dir = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
                                    'Incomplete Downloads')
        # Create the download directory if it doesn't already exist.
        if not os.path.exists(download_dir):
            fileutil.makedirs(download_dir)
        filename = self.shortFilename + suffix
        if not torrent:
            # this is an ascii filename and needs to be fixed
            filename = clean_filename(filename)
        self.filename = next_free_filename(
            os.path.join(download_dir, filename))

    def move_to_movies_directory(self):
        """Move our downloaded file from the Incomplete Downloads
        directory to the movies directory.
        """
        if chatter:
            logging.info("move_to_movies_directory: filename is %s",
                         self.filename)
        self.move_to_directory(config.get(prefs.MOVIES_DIRECTORY))

    def move_to_directory(self, directory):
        check_f(directory)
        if self.channelName:
            channel_name = filter_directory_name(self.channelName)
            # bug 10769: shutil and windows has problems with long
            # filenames, so we clip the directory name.
            if len(channel_name) > 80:
                channel_name = channel_name[:80]
            directory = os.path.join(directory, channel_name)
            if not os.path.exists(directory):
                try:
                    fileutil.makedirs(directory)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    pass
        newfilename = os.path.join(directory, self.shortFilename)
        if newfilename == self.filename:
            return
        newfilename = next_free_filename(newfilename)
        def callback():
            self.filename = newfilename
            self.update_client()
        fileutil.migrate_file(self.filename, newfilename, callback)

    def get_eta(self):
        """Returns a float with the estimated number of seconds left.
        """
        if self.totalSize == -1:
            return -1
        rate = self.get_rate()
        if rate > 0:
            return (self.totalSize - self.currentSize) / rate
        else:
            return 0

    def get_rate(self):
        """Returns a float with the download rate in bytes per second
        """
        if self.endTime != self.startTime:
            rate = self.currentSize / (self.endTime - self.startTime)
        else:
            rate = self.rate
        return rate

    def retry_download(self):
        self.retryDC = None
        self.start(resume=False)

    def handle_temporary_error(self, shortReason, reason):
        self.state = u"offline"
        self.endTime = self.startTime = 0
        self.rate = 0
        self.reasonFailed = reason
        self.shortReasonFailed = shortReason
        self.retryCount = self.retryCount + 1
        if self.retryCount >= len(RETRY_TIMES):
            self.retryCount = len(RETRY_TIMES) - 1
        self.retryDC = eventloop.add_timeout(
            RETRY_TIMES[self.retryCount], self.retry_download,
            "Logarithmic retry")
        now = datetime.datetime.now()
        self.retryTime = now + datetime.timedelta(seconds=RETRY_TIMES[self.retryCount])
        logging.info("Temporary error: '%s' '%s'.  retrying at %s %s",
                     shortReason, reason, self.retryTime, self.retryCount)
        self.update_client()

    def handle_error(self, shortReason, reason):
        self.state = u"failed"
        self.reasonFailed = reason
        self.shortReasonFailed = shortReason
        self.update_client()

    def handle_network_error(self, error):
        if isinstance(error, httpclient.NetworkError):
            if ((isinstance(error, httpclient.MalformedURL)
                 or isinstance(error, httpclient.UnexpectedStatusCode))):
                self.handle_error(error.getFriendlyDescription(),
                                  error.getLongDescription())
            else:
                self.handle_temporary_error(error.getFriendlyDescription(),
                                            error.getLongDescription())
        else:
            logging.info("WARNING: grab_url errback not called with "
                         "NetworkError")
            self.handle_error(str(error), str(error))

    def handle_generic_error(self, longDescription):
        self.handle_error(_("Error"), longDescription)

    def accept_download_size(self, size):
        """Checks the download file size to see if we can accept it
        based on the user disk space preservation preference
        """
        accept = True
        if config.get(prefs.PRESERVE_DISK_SPACE):
            if size < 0:
                size = 0
            preserved = (config.get(prefs.PRESERVE_X_GB_FREE) *
                         1024 * 1024 * 1024)
            available = get_available_bytes_for_movies() - preserved
            accept = (size <= available)
        return accept

class HTTPDownloader(BGDownloader):
    CHECK_STATS_TIMEOUT = 1.0

    def __init__(self, url=None, dlid=None, restore=None,
                 expectedContentType=None):
        self.retryDC = None
        self.channelName = None
        self.expectedContentType = expectedContentType
        if restore is not None:
            if not isinstance(restore.get('totalSize', 0), int):
                # Sometimes restoring old downloaders caused errors
                # because their totalSize wasn't an int.  (see #3965)
                restore['totalSize'] = int(restore['totalSize'])
            self.__dict__.update(restore)
            self.restartOnError = True
        else:
            BGDownloader.__init__(self, url, dlid)
            self.restartOnError = False
        self.client = None
        self.rate = 0
        if self.state == 'downloading':
            self.start_download()
        elif self.state == 'offline':
            self.start()
        else:
            self.update_client()

    def start_new_download(self):
        """Start a download, discarding any existing data"""
        self.currentSize = 0
        self.totalSize = -1
        self.start_download(resume=False)

    def start_download(self, resume=True):
        if self.retryDC:
            self.retryDC.cancel()
            self.retryDC = None
        if resume:
            resume = self._resume_sanity_check()

        logging.info("start_download: %s", self.url)

        self.client = httpclient.grab_url(
            self.url, self.on_download_finished, self.on_download_error,
            header_callback=self.on_headers, write_file=self.filename,
            resume=resume)
        self.update_client()
        eventloop.add_timeout(self.CHECK_STATS_TIMEOUT, self.update_stats,
                'update http downloader stats')

    def _resume_sanity_check(self):
        """Do sanity checks to test if we should try HTTP Resume.

        :returns: If we should still try HTTP resume
        """
        if not os.path.exists(self.filename):
            return False
        # sanity check that the file we're resuming from is the right
        # size.  In particular, before the libcurl change, we would
        # preallocate the entire file, so we need to undo this.
        file_size = os.stat(self.filename)[stat.ST_SIZE]
        if file_size > self.currentSize:
            # use logging.info rather than warn, since this is the
            # usual case from upgrading from 3.0.x to 3.1
            logging.info("File larger than currentSize: truncating.  "
                    "url: %s, path: %s.", self.url, self.filename)
            f = open(self.filename, "ab")
            f.truncate(self.currentSize)
            f.close()
        elif file_size < self.currentSize:
            # Data got deleted somehow.  Let's start over.
            logging.warn("File doesn't contain enough data to resume.  "
                    "url: %s, path: %s.", self.url, self.filename)
            return False
        return True

    def destroy_client(self):
        """update the stats before we throw away the client.
        """
        self.update_stats()
        self.client = None

    def cancel_request(self, remove_file=False):
        if self.client is not None:
            self.client.cancel(remove_file=remove_file)
            self.destroy_client()
        # if it's in a retrying state, we want to nix that, too
        if self.retryDC:
            self.retryDC.cancel()
            self.retryDC = None

    def handle_error(self, shortReason, reason):
        BGDownloader.handle_error(self, shortReason, reason)
        self.cancel_request()
        if os.path.exists(self.filename):
            try:
                fileutil.remove(self.filename)
            except OSError:
                pass
        self.currentSize = 0
        self.totalSize = -1

    def handle_temporary_error(self, shortReason, reason):
        BGDownloader.handle_temporary_error(self, shortReason, reason)
        self.cancel_request()

    def handle_write_error(self, error):
        text = (_("Could not write to %(filename)s") %
                {"filename": stringify(self.filename)})
        self.handle_generic_error(text)

    def on_headers(self, info):
        if 'total-size' in info:
            self.totalSize = info['total-size']
        if not self.accept_download_size(self.totalSize):
            self.handle_error(_("Not enough disk space"),
                _("%(amount)s MB required to store this video") %
                  {"amount": self.totalSize / (2 ** 20)})
            return
        # We should successfully download the file.  Reset retryCount
        # and accept defeat if we see an error.
        self.retryCount = -1
        self.restartOnError = False
        # update shortFilename based on the headers.  This will affect
        # how we move the file once the download is finished
        self.shortFilename = clean_filename(info['filename'])

    def on_download_error(self, error):
        if isinstance(error, httpclient.ResumeFailed):
            # try starting from scratch
            self.currentSize = 0
            self.totalSize = -1
            self.start_new_download()
        elif self.restartOnError:
            self.restartOnError = False
            self.start_download()
        else:
            self.destroy_client()
            self.handle_network_error(error)

    def on_download_finished(self, response):
        self.destroy_client()
        self.state = "finished"
        self.endTime = clock()
        # bug 14131 -- if there's nothing here, treat it like a temporary
        # error
        if self.currentSize == 0:
            self.handle_network_error(httpclient.PossiblyTemporaryError(_("no content")))

        else:
            if self.totalSize == -1:
                self.totalSize = self.currentSize
            try:
                self.move_to_movies_directory()
            except IOError, e:
                self.handle_write_error(e)
        self.update_client()

    def get_status(self):
        data = BGDownloader.get_status(self)
        data['dlerType'] = 'HTTP'
        return data

    def update_stats(self):
        """Update the download rate and eta based on receiving length
        bytes.
        """
        if self.client is None or self.state != 'downloading':
            return
        stats = self.client.get_stats()
        self.currentSize = stats.downloaded + stats.initial_size
        self.rate = stats.download_rate
        eventloop.add_timeout(self.CHECK_STATS_TIMEOUT, self.update_stats,
                'update http downloader stats')
        DOWNLOAD_UPDATER.queue_update(self)

    def pause(self):
        """Pauses the download.
        """
        if self.state != "stopped":
            self.cancel_request()
            self.state = "paused"
            self.update_client()

    def stop(self, delete):
        """Stops the download and removes the partially downloaded
        file.
        """
        if self.state == 'finished':
            if delete:
                try:
                    if fileutil.isdir(self.filename):
                        fileutil.rmtree(self.filename)
                    else:
                        fileutil.remove(self.filename)
                except OSError:
                    pass
        else:
            # Cancel the request, don't keep around partially
            # downloaded data
            self.cancel_request(remove_file=True)
        self.currentSize = 0
        self.state = "stopped"
        self.update_client()

    def stop_upload(self):
        # HTTP downloads never upload.
        pass

    def start(self, resume=False):
        """Continues a paused or stopped download thread.
        """
        if self.state in ('paused', 'stopped', 'offline'):
            self.state = "downloading"
            self.start_download(resume=resume)

    def shutdown(self):
        self.cancel_request()
        self.update_client()

class BTDownloader(BGDownloader):
    # update fast resume every 5 minutes
    FAST_RESUME_UPDATE_INTERVAL = 60 * 5

    def __init__(self, url=None, item=None, restore=None):
        self.metainfo = None
        self.torrent = None
        self.rate = self.eta = 0
        self.upRate = self.uploaded = 0
        self.activity = None
        self.fastResumeData = None
        self.retryDC = None
        self.channelName = None
        self.uploadedStart = 0
        self.restarting = False
        self.seeders = -1
        self.leechers = -1
        self.last_fast_resume_update = clock()
        if restore is not None:
            self.firstTime = False
            self.restore_state(restore)
        else:
            self.firstTime = True
            BGDownloader.__init__(self,url,item)
            self.run_downloader()

    def _start_torrent(self):
        try:
            torrent_info = lt.torrent_info(lt.bdecode(self.metainfo))
            duplicate = TORRENT_SESSION.find_duplicate_torrent(torrent_info)
            if duplicate is not None:
                c = command.DuplicateTorrent(daemon.LAST_DAEMON,
                        duplicate.dlid, self.dlid)
                c.send()
                return
            self.totalSize = torrent_info.total_size()

            if self.firstTime and not self.accept_download_size(self.totalSize):
                self.handle_error(
                    _("Not enough disk space"),
                    _("%(amount)s MB required to store this video",
                      {"amount": self.totalSize / (2 ** 20)})
                    )
                return

            save_path = os.path.dirname(fileutil.expand_filename(self.filename))
            if self.fastResumeData:
                self.torrent = TORRENT_SESSION.session.add_torrent(
                    torrent_info, save_path, lt.bdecode(self.fastResumeData),
                    lt.storage_mode_t.storage_mode_allocate)
                self.torrent.resume()
            else:
                self.torrent = TORRENT_SESSION.session.add_torrent(
                    torrent_info, save_path, None,
                    lt.storage_mode_t.storage_mode_allocate)
            try:
                if (lt.version_major, lt.version_minor) > (0, 13):
                    logging.debug(
                        "setting libtorrent auto_managed to False")
                    self.torrent.auto_managed(False)
            except AttributeError:
                logging.warning("libtorrent module doesn't have "
                                "version_major or version_minor")
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            self.handle_error(_('BitTorrent failure'),
                              _('BitTorrent failed to startup'))
            logging.exception("Exception thrown in _start_torrent")
        else:
            TORRENT_SESSION.add_torrent(self)

    def _shutdown_torrent(self):
        try:
            TORRENT_SESSION.remove_torrent(self)
            if self.torrent is not None:
                self.torrent.pause()
                self.update_fast_resume_data()
                TORRENT_SESSION.session.remove_torrent(self.torrent, 0)
                self.torrent = None
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error shutting down torrent")

    def _pause_torrent(self):
        try:
            TORRENT_SESSION.remove_torrent(self)
            if self.torrent is not None:
                self.torrent.pause()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error pausing torrent")

    def _resume_torrent(self):
        if self.torrent is None:
            self._start_torrent()
            return

        try:
            self.torrent.resume()
            TORRENT_SESSION.add_torrent(self)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error resuming torrent")

    def update_status(self):
        """
        activity -- string specifying what's currently happening or None for
                normal operations.
        upRate -- upload rate in B/s
        downRate -- download rate in B/s
        upTotal -- total MB uploaded
        downTotal -- total MB downloaded
        fractionDone -- what portion of the download is completed.
        timeEst -- estimated completion time, in seconds.
        totalSize -- total size of the torrent in bytes
        """
        status = self.torrent.status()
        self.totalSize = status.total_wanted
        self.rate = status.download_payload_rate
        self.upRate = status.upload_payload_rate
        self.uploaded = status.total_payload_upload + self.uploadedStart
        self.seeders = status.num_complete
        self.leechers = status.num_incomplete
        try:
            self.eta = ((status.total_wanted - status.total_wanted_done) /
                        float(status.download_payload_rate))
        except ZeroDivisionError:
            self.eta = 0
        if status.state == lt.torrent_status.states.queued_for_checking:
            self.activity = "waiting to check existing files"
        elif status.state == lt.torrent_status.states.checking_files:
            self.activity = "checking existing files"
        elif status.state == lt.torrent_status.states.allocating:
            self.activity = "allocating disk space"
        else:
            self.activity = None
        self.currentSize = status.total_wanted_done
        if ((self.state == "downloading"
             and status.state == lt.torrent_status.states.seeding)):
            self.move_to_movies_directory()
            self.state = "uploading"
            self.endTime = clock()
            self.update_client()
        else:
            DOWNLOAD_UPDATER.queue_update(self)

        if config.get(prefs.LIMIT_UPLOAD_RATIO):
            if status.state == lt.torrent_status.states.seeding:
                if ((float(self.uploaded) / self.totalSize >
                     config.get(prefs.UPLOAD_RATIO))):
                    self.stop_upload()

        if self.should_update_fast_resume_data():
            self.update_fast_resume_data()

    def should_update_fast_resume_data(self):
        return (clock() - self.last_fast_resume_update >
                self.FAST_RESUME_UPDATE_INTERVAL)

    def update_fast_resume_data(self):
        self.last_fast_resume_update = clock()
        self.fastResumeData = lt.bencode(self.torrent.write_resume_data())

    def handle_error(self, shortReason, reason):
        self._shutdown_torrent()
        BGDownloader.handle_error(self, shortReason, reason)

    def handle_temporary_error(self, shortReason, reason):
        self._shutdown_torrent()
        BGDownloader.handle_temporary_error(self, shortReason, reason)

    def move_to_directory(self, directory):
        if self.state in ('uploading', 'downloading'):
            self._shutdown_torrent()
            BGDownloader.move_to_directory(self, directory)
            self._resume_torrent()
        else:
            BGDownloader.move_to_directory(self, directory)

    def restore_state(self, data):
        self.__dict__.update(data)
        self.rate = self.eta = 0
        self.upRate = 0
        self.uploadedStart = self.uploaded
        if self.state in ('downloading', 'uploading'):
            self.run_downloader(done=True)
        elif self.state == 'offline':
            self.start()

    def get_status(self):
        data = BGDownloader.get_status(self)
        data['upRate'] = self.upRate
        data['uploaded'] = self.uploaded
        data['metainfo'] = self.metainfo
        data['fastResumeData'] = self.fastResumeData
        data['activity'] = self.activity
        data['dlerType'] = 'BitTorrent'
        data['seeders'] = self.seeders
        data['leechers'] = self.leechers
        return data

    def get_rate(self):
        return self.rate

    def get_eta(self):
        return self.eta

    def pause(self):
        self.state = "paused"
        self.restarting = True
        self._pause_torrent()
        self.update_client()

    def stop(self, delete):
        self.state = "stopped"
        self._shutdown_torrent()
        self.update_client()
        if delete:
            try:
                if fileutil.isdir(self.filename):
                    fileutil.rmtree(self.filename)
                else:
                    fileutil.remove(self.filename)
            except OSError:
                pass

    def stop_upload(self):
        self.state = "finished"
        self._shutdown_torrent()
        self.update_client()

    def pause_upload(self):
        self.state = "uploading-paused"
        self._shutdown_torrent()
        self.update_client()

    def start(self, resume=False):
        # for BT downloads, resume doesn't mean anything, so we
        # ignore it.
        if self.state not in ('paused', 'stopped', 'offline'):
            return

        self.state = "downloading"
        if self.retryDC:
            self.retryDC.cancel()
            self.retryDC = None
        self.update_client()
        self.get_metainfo()

    def shutdown(self):
        self._shutdown_torrent()
        self.update_client()

    def got_metainfo(self):
        # FIXME: If the client is stopped before a BT download gets
        #        its metadata, we never run this. It's not a huge deal
        #        because it only affects the incomplete filename
        if not self.restarting:
            try:
                metainfo = lt.bdecode(self.metainfo)
                # if we don't get valid torrent metadata back, then the
                # metainfo is None.  treat that like a runtime error.
                if not metainfo:
                    raise RuntimeError()
                name = metainfo['info']['name']
            except RuntimeError:
                self.handle_corrupt_torrent()
                return
            self.shortFilename = utf8_to_filename(name)
            self.pick_initial_filename(suffix="", torrent=True)
        self.update_client()
        self._resume_torrent()

    def handle_corrupt_torrent(self):
        self.handle_error(
            _("Corrupt Torrent"),
            _("The torrent file at %(url)s was not valid",
              {"url": stringify(self.url)})
            )

    def handle_metainfo(self, metainfo):
        self.metainfo = metainfo
        self.got_metainfo()

    def check_description(self, data):
        if len(data) > MAX_TORRENT_SIZE or data[0] != 'd':
            # Bailout if we get too much data or it doesn't begin with
            # "d" (see #12301 for details)
            eventloop.add_idle(self.handle_corrupt_torrent,
                               'description check failed')
            return False
        else:
            return True

    def on_metainfo_download(self, info):
        self.handle_metainfo(info['body'])

    def on_metainfo_download_error(self, exception):
        self.handle_network_error(exception)

    def get_metainfo(self):
        if self.metainfo is None:
            if self.url.startswith('file://'):
                path = get_file_url_path(self.url)
                try:
                    metainfoFile = open(path, 'rb')
                except IOError:
                    self.handle_error(_("Torrent file deleted"),
                                     _("The torrent file for this item was deleted "
                                       "outside of %(appname)s.",
                                       {"appname": config.get(prefs.SHORT_APP_NAME)}
                                       ))

                    return
                try:
                    metainfo = metainfoFile.read()
                finally:
                    metainfoFile.close()

                self.handle_metainfo(metainfo)
            else:
                self.description_client = httpclient.grab_url(self.url,
                        self.on_metainfo_download,
                        self.on_metainfo_download_error,
                        content_check_callback=self.check_description)
        else:
            self.got_metainfo()

    def run_downloader(self, done=False):
        self.restarting = done
        self.update_client()
        self.get_metainfo()
