import os

from miro import app
from miro import downloader
from miro import eventloop
from miro import models
from miro import prefs
from miro.dl_daemon import command
from miro.plat import resources
from miro.test import testobjects
from miro.test.framework import MiroTestCase

class DownloaderTest(MiroTestCase):
    """Test feeds that download things.
    """
    def setUp(self):
        MiroTestCase.setUp(self)
        self.mock_grab_headers = self.patch_for_test(
            'miro.httpclient.grab_headers')
        self.mock_try_scraping_url = self.patch_for_test(
            'miro.flashscraper.try_scraping_url')
        self.mock_send = self.patch_for_test(
            'miro.dl_daemon.command.Command.send')
        self.feed = testobjects.make_feed()
        self.url = u'http://example.com/my-video.mp4'
        self.item = testobjects.make_item(self.feed, u'my item', url=self.url)
        self.downloading_path = os.path.join(self.tempdir,
                                             'Incomplete Downloads',
                                             'download.mp4')
        self.final_path = os.path.join(self.tempdir, 'download.mp4')

    def start_download(self):
        self.item.download()
        self.dlid = self.item.downloader.dlid
        self.run_content_type_check()
        self.run_flash_scrape()
        self.run_daemon_commands()

    def run_content_type_check(self):
        self.assertEquals(self.mock_grab_headers.call_count, 1)
        url, callback, errback = self.mock_grab_headers.call_args[0]
        self.assertEquals(url, self.url)
        self.mock_grab_headers.reset_mock()
        callback({
            'status': 200,
            'updated-url': self.url,
            'content-type': 'video/mp4'
        })

    def run_flash_scrape(self):
        self.assertEquals(self.mock_try_scraping_url.call_count, 1)
        url, callback = self.mock_try_scraping_url.call_args[0]
        self.assertEquals(url, self.url)
        self.mock_try_scraping_url.reset_mock()
        callback(self.url)

    def run_daemon_commands(self):
        app.download_state_manager.send_updates()
        self.assertEquals(self.mock_send.call_count, 1)
        cmd = self.mock_send.call_args[0][0]
        self.assertEquals(type(cmd), command.DownloaderBatchCommand)
        arg = cmd.args[0]
        self.assertEquals(arg.keys(), [self.dlid])
        self.assertEquals(arg[self.dlid][0],
                          command.DownloaderBatchCommand.RESUME)
        self.assertEquals(arg[self.dlid][1]['url'], self.url)

    def update_status(self, download_progress, elapsed_time):
        # define some arbitrary constants
        total_size = 100000
        start_time = 1000
        # calculate values based on download_progress/elapsed_time
        current_size = int(total_size * download_progress)
        rate = current_size / elapsed_time
        eta = int((total_size - current_size) / rate)
        if download_progress < 1.0:
            state = u'downloading'
            end_time = None
            filename = self.downloading_path
        else:
            end_time = start_time + elapsed_time
            state = u'finished'
            filename = self.final_path

        downloader.RemoteDownloader.update_status({
            'dlid': self.dlid,
            'url': self.url,
            'state': state,
            'total_size': total_size,
            'current_size': current_size,
            'eta': eta,
            'rate': rate,
            'upload_size': 0,
            'filename': filename,
            'start_time': start_time,
            'end_time': end_time,
            'short_filename': 'download.mp4',
            'reason_failed': None,
            'short_reason_failed': None,
            'type': None,
            'retry_time': None,
            'retry_count': None,
        }, cmd_done=True)

    def check_download_in_progress(self):
        self.assertEquals(self.item.downloader.get_state(), u'downloading')
        self.assertEquals(self.item.get_state(), u'downloading')

    def check_download_finished(self):
        self.assertEquals(self.item.downloader.get_state(), u'finished')
        self.assertEquals(self.item.get_state(), u'newly-downloaded')

    def run_download(self):
        self.start_download()
        self.check_download_in_progress()
        self.update_status(0.3, 10)
        self.check_download_in_progress()
        self.update_status(0.5, 20)
        self.check_download_in_progress()
        self.update_status(0.9, 30)
        self.check_download_in_progress()
        with open(self.final_path, 'w') as f:
            f.write("bogus data")
        self.update_status(1.0, 40)
        self.check_download_finished()

    def test_download(self):
        self.run_download()

    def test_delete(self):
        self.run_download()
        self.assertEquals(self.feed.downloaded_items.count(), 1)
        self.item.expire()
        self.assertEquals(self.feed.downloaded_items.count(), 0)

    ## def test_resume(self):
    ##     # FIXME - implement this
    ##     pass

    ## def test_resume_fail(self):
    ##     # FIXME - implement this
    ##     pass
