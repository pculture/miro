"""Glue code to handle BitTorrent stuff.  Most of this comes from download.py
in the BitTorrent library.
"""

from urlparse import urljoin
from binascii import b2a_hex
from sha import sha
from os import path, makedirs
from socket import error as socketerror
from random import seed
from threading import Thread, Event, Lock
from time import time
from Queue import Queue
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1

from BitTorrent.bitfield import Bitfield
from BitTorrent.btformats import check_message
from BitTorrent.Choker import Choker
from BitTorrent.Storage import Storage
from BitTorrent.StorageWrapper import StorageWrapper
from BitTorrent.Uploader import Upload
from BitTorrent.Downloader import Downloader
from BitTorrent.Connecter import Connecter
from BitTorrent.Encrypter import Encoder
from BitTorrent.RawServer import RawServer
from BitTorrent.Rerequester import Rerequester
from BitTorrent.DownloaderFeedback import DownloaderFeedback
from BitTorrent.RateMeasure import RateMeasure
from BitTorrent.CurrentRateMeasure import Measure
from BitTorrent.PiecePicker import PiecePicker
from BitTorrent.bencode import bencode, bdecode
from BitTorrent.download import defaults
from BitTorrent import version

import config as dtv_config
import prefs

config = {}
for key, default, description in defaults:
    config[key] = default
config['report_hash_failures'] = True
storage_lock = Lock()

class TorrentDownload:
    def __init__(self, torrent_data, download_to, fast_resume_data=None):
        """Create a new torrent.  torrent_data is the contents of a torrent
        file/url.  download_to is the file/directory to save the torrent to.
        fast_resume_data is data used to quickly restart the torrent, it's
        returned by the shutdown() method.
        """

        self.doneflag = Event()
        self.finflag = Event()
        self.torrent_data = torrent_data
        self.download_to = download_to
        self.fast_resume_data = fast_resume_data
        self.fast_resume_queue = Queue()
        self.rawserver = RawServer(self.doneflag,
                config['timeout_check_interval'], config['timeout'],
                errorfunc=self.on_error, maxconnects=config['max_allow_in'])
        self.thread = None
        self.current_status = {}
        self.status_callback = None
        # we set time_est_func to a real function in download().  For now use
        # a placeholder function
        self.time_est_func = lambda: 0
        self.last_up_total = self.last_down_total = 0.0
        self.last_activity = None
        self.rawserver_started = False
        self.minport = dtv_config.get(prefs.BT_MIN_PORT)
        self.maxport = dtv_config.get(prefs.BT_MAX_PORT)

    def start(self):
        """Start downloading the torrent."""
        self.thread = Thread(target=self.download)
        filename = path.basename(self.download_to)
        self.thread.setName("BitTorrent Downloader - %s" % filename)
        self.thread.start()

    def shutdown(self):
        """Stop downloading the torrent.

        Returns a string that can be used as fast resume data.
        """

        self.doneflag.set()
        self.rawserver.wakeup()
        if self.rawserver_started:
            return self.fast_resume_queue.get()
        else:
            return self.fast_resume_data

    def parse_fast_resume_data(self, total_pieces):
        already_got = None
        mtimes = {}
        if self.fast_resume_data is not None:
            try:
                fast_resume = bdecode(self.fast_resume_data)
                already_got = fast_resume['already_got']
                mtimes = fast_resume['mtimes']
            except:
                import traceback
                print "WARNING: ERROR parsing fast resume data"
                traceback.print_exc(1)
                self.fast_resume_data = None
        self.pieces_already_got = Bitfield(total_pieces, already_got)
        self.fast_resume_mtimes = mtimes

    def skip_hash_check(self, index, files):
        if not self.pieces_already_got[index]:
            return False
        for f in files:
            if path.getmtime(f) > self.fast_resume_mtimes.get(f, 0):
                return False
        return True

    def set_status_callback(self, func):
        """Register a callback function.  func will be called whenever the
        torrent download status changes and periodically while the torrent
        downloads.  It will be passed a dict with the following attributes:

        activity -- string specifying what's currently happening or None for
                normal operations.  
        upRate -- upload rate
        downRate -- download rate in kb/s
        upTotal -- total kb uploaded
        downTotal -- total kb downloaded
        fractionDone -- what portion of the download is completed.
        timeEst -- estimated completion time, in seconds.
        totalSize -- total size of the torrent in bytes
        """
        self.status_callback = func

    def on_error(self, message):
        print "WARNING BitTorrent error: ", message

    def on_status(self, status_dict):
        status = {
            'upRate': status_dict.get('upRate', 0),
            'downRate': status_dict.get('downRate', 0),
            'upTotal': status_dict.get('upTotal', self.last_up_total),
            'downTotal': status_dict.get('downTotal', self.last_down_total),
            'timeEst': self.time_est_func(),
            'totalSize': self.total_size,
        }

        if status['timeEst'] is None:
            status['timeEst'] = 0
        if self.finflag.isSet():
            status['fractionDone'] = 1.0
        else:
            status['fractionDone'] = status_dict.get('fractionDone', 0.0)
        if status['downRate'] > 0 or status['upRate'] > 0:
            status['activity'] = None
        else:
            status['activity'] = status_dict.get('activity',
                    self.last_activity)

        self.last_up_total = status['upTotal']
        self.last_down_total = status['downTotal']
        self.last_activity = status['activity']
        self.status_callback(status)

    def filefunc(self, file, length, saveas, isdir):
        self.total_size = length
        return self.download_to

    def download(self):
        # Basically coppied from from the download() function in
        # BitTorrent.download.  Modified slightly to work with democracy.
        spewflag = Event()
        try:
            response = bdecode(self.torrent_data)
            check_message(response)
        except ValueError, e:
            self.on_error("got bad file info - " + str(e))
            return
        
        try:
            def make(f, forcedir = False):
                if not forcedir:
                    f = path.split(f)[0]
                if f != '' and not path.exists(f):
                    makedirs(f)
                    
            info = response['info']
            if info.has_key('length'):
                file_length = info['length']
                file = self.filefunc(info['name'], file_length, 
                        config['saveas'], False)
                if file is None:
                    return
                make(file)
                files = [(file, file_length)]
            else:
                file_length = 0
                for x in info['files']:
                    file_length += x['length']
                file = self.filefunc(info['name'], file_length, 
                        config['saveas'], True)
                if file is None:
                    return
      
                make(file, True)
                
                files = []
                for x in info['files']:
                    n = file
                    for i in x['path']:
                        n = path.join(n, i)
                    files.append((n, x['length']))
                    make(n)
        except OSError, e:
            self.on_error("Couldn't allocate dir - " + str(e))
            return
        
        finflag = self.finflag
        ann = [None]
        myid = 'M' + version.replace('.', '-')
        myid = myid + ('-' * (8 - len(myid))) + b2a_hex(sha(repr(time()) + ' ' + str(getpid())).digest()[-6:])
        seed(myid)
        pieces = [info['pieces'][x:x+20] for x in xrange(0, 
            len(info['pieces']), 20)]
        self.parse_fast_resume_data(len(pieces))
        def failed(reason):
            self.doneflag.set()
            if reason is not None:
                self.on_error(reason)
        rawserver = self.rawserver
        storage_lock.acquire()
        try:
            try:
                try:
                    storage = Storage(files, open, path.exists, path.getsize)
                except IOError, e:
                    self.on_error('trouble accessing files - ' + str(e))
                    return
                def finished(finflag = finflag, ann = ann, storage = storage):
                    finflag.set()
                    try:
                        storage.set_readonly()
                    except (IOError, OSError), e:
                        self.on_error('trouble setting readonly at end - ' + str(e))
                    if ann[0] is not None:
                        ann[0](1)
                rm = [None]
                def data_flunked(amount, rm = rm, report_hash_failures = config['report_hash_failures']):
                    if rm[0] is not None:
                        rm[0](amount)
                    if report_hash_failures:
                        self.on_error('a piece failed hash check, re-downloading it')
                storagewrapper = StorageWrapper(storage,
                        config['download_slice_size'], pieces, 
                        info['piece length'], finished, failed, self.on_status,
                        self.doneflag, config['check_hashes'], data_flunked,
                        self.skip_hash_check)
            except ValueError, e:
                failed('bad data - ' + str(e))
            except IOError, e:
                failed('IOError - ' + str(e))
        finally:
            storage_lock.release()
        if self.doneflag.isSet():
            return

        e = 'maxport less than minport - no ports to check'

        for listen_port in xrange(self.minport, self.maxport + 1):
            try:
                rawserver.bind(listen_port, config['bind'])
                break
            except socketerror, e:
                pass
        else:
            self.on_error("Couldn't listen - " + str(e))
            return

        choker = Choker(config['max_uploads'], rawserver.add_task, finflag.isSet, 
            config['min_uploads'])
        upmeasure = Measure(config['max_rate_period'], 
            config['upload_rate_fudge'])
        downmeasure = Measure(config['max_rate_period'])
        def make_upload(connection, choker = choker, 
                storagewrapper = storagewrapper, 
                max_slice_length = config['max_slice_length'],
                max_rate_period = config['max_rate_period'],
                fudge = config['upload_rate_fudge']):
            return Upload(connection, choker, storagewrapper, 
                max_slice_length, max_rate_period, fudge)
        ratemeasure = RateMeasure(storagewrapper.get_amount_left())
        self.time_est_func = ratemeasure.get_time_left
        rm[0] = ratemeasure.data_rejected
        picker = PiecePicker(len(pieces), config['rarest_first_cutoff'])
        for i in xrange(len(pieces)):
            if storagewrapper.do_I_have(i):
                picker.complete(i)
        downloader = Downloader(storagewrapper, picker,
            config['request_backlog'], config['max_rate_period'],
            len(pieces), downmeasure, config['snub_time'], 
            ratemeasure.data_came_in)
        connecter = Connecter(make_upload, downloader, choker,
            len(pieces), upmeasure, config['max_upload_rate'] * 1024, rawserver.add_task)
        infohash = sha(bencode(info)).digest()
        encoder = Encoder(connecter, rawserver, 
            myid, config['max_message_length'], rawserver.add_task, 
            config['keepalive_interval'], infohash, config['max_initiate'])
        rerequest = Rerequester(response['announce'],
                config['rerequest_interval'], rawserver.add_task,
                connecter.how_many_connections, config['min_peers'],
                encoder.start_connection, rawserver.add_task,
                storagewrapper.get_amount_left, upmeasure.get_total,
                downmeasure.get_total, listen_port, config['ip'], myid,
                infohash, config['http_timeout'], self.on_error,
                config['max_initiate'], self.doneflag, upmeasure.get_rate,
                downmeasure.get_rate, encoder.ever_got_incoming)
        if config['spew']:
            spewflag.set()
        DownloaderFeedback(choker, rawserver.add_task, self.on_status, 
            upmeasure.get_rate, downmeasure.get_rate, 
            upmeasure.get_total, downmeasure.get_total, ratemeasure.get_time_left, 
            ratemeasure.get_size_left, file_length, finflag,
            config['display_interval'], spewflag)
        self.on_status({"activity" : 'connecting to peers'})
        ann[0] = rerequest.announce
        rerequest.begin()
        self.rawserver_started = True
        try:
            rawserver.listen_forever(encoder)
        finally:
            fast_resume_data = {
                'already_got': storagewrapper.get_have_list(),
                'mtimes': dict([(f, path.getmtime(f)) for f, size in files]),
            }
            self.fast_resume_queue.put(bencode(fast_resume_data))
        storage.close()
        rerequest.announce(2)
