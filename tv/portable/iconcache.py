import item
import os
import threading
from download_utils import grabURL
from Queue import Queue

class IconCacheUpdater:
    def __init__ (self):
        self.idle = []
        self.vital = []
        self.cond = threading.Condition()

        thread = threading.Thread(target=self.consumer_thread,\
                                  name="Icon Cache Updater")
        thread.setDaemon(True)
        thread.start()

    def requestUpdate (self, item, is_vital):
        self.cond.acquire()
        if (is_vital):
            self.vital.prepend(item)
        else:
            self.idle.prepend(item)
        self.cond.notify()
        self.cond.release()

    def consumer_thread (self):
        while (True):
            self.cond.acquire()
            while (len(vital) == 0 and len(idle) == 0):
                self.cond.wait()
            if (len(vital) > 0):
                item = vital.pop()
            else
                item = idle.pop()
            self.cond.release()
            item.cache.update (lambda : item.url)


filename_lock = threading.Lock()
class IconCache:
    def __init__ (self, url):
        self.etag = None
        self.modified = None
        self.filename = None
        self.url = url
        self.updated = False
        self.lock = threading.Lock()
    ##
    # Finds a filename that's unused and similar the the file we want
    # to download
    def nextFreeFilename(self, name):
        if not access(name,F_OK):
            return name
        parts = name.split('.')
        count = 1
        if len(parts) == 1:
            newname = "%s.%s" % (name, count)
            while access(newname,F_OK):
                count += 1
                newname = "%s.%s" % (name, count)
        else:
            parts[-1:-1] = [str(count)]
            newname = '.'.join(parts)
            while access(newname,F_OK):
                count += 1
                parts[-2] = str(count)
                newname = '.'.join(parts)
        return newname

    def update (self, url_func, db_write_lock = None, db_read_lock = None):
        try:
            self.lock.acquire()
            # Read all data at once so we can free up the database.
            try:
                if (db_read_lock):
                    db_read_lock.acquire()
                filename = self.filename
                etag = self.etag
                modified = self.modified
                updated = self.updated
                old_url = self.url
                url = url_func()
            finally:
                if (db_read_lock):
                    db_read_lock.release()

            # Only verify each icon once per run unless the url changes
            if (updated and url == old_url):
                return

            cachedir = os.path.join (config.get (config.SUPPORT_DIRECTORY), "icon-cache")
    
            if (not os.path.isdir (cachedir))
                os.makedirs (cachedir)
    
            # If we have sufficiently cached data, let the server know that.
            if (url == old_url and filename and os.access (filename, os.R_OK))
                info = grabURL (url, etag = etag, modified = modified)
            else:
                info = grabURL (url)
    
            # Error during download.  To reflect that, clear the cache if
            # there was one before.
            if (info == None):
                try:
                    if (filename):
                        os.remove (filename)
                except:
                    pass
                filename = None
                try:
                    if (db_write_lock):
                        db_write_lock.acquire()
                    self.filename = filename
                finally:
                    if (db_write_lock):
                        db_write_lock.release()
                return
    
            # Our cache is good.  Hooray!
            if (info['status'] == 304):
                return
    
            # We have to update it, and if we can't write to the file, we
            # should pick a new filename.
            if (filename and not os.access (filename, os.R_OK | os.W_OK)):
                filename = None
    
            # Download to a temp file.
            if (filename):
                tmp_filename = filename + ".part"
            else:
                tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"
    
            # Once we open the output file, we can release the filename
            # lock, since the file has been created.
            try:
                filename_lock.acquire()
                tmp_filename = self.nextFreeFilename (tmp_filename)
                output = file (tmp_filename)
            finally:
                filename_lock.release()
    
            # Do the download without the filename_lock in case there are multiple threads downloading.
            input = info["file-handle"]
            data = input.read(1024)
            while (data and data != ""):
                output.write(data)
                data = input.read(1024)
            output.close()
            input.close()
    
            # We're move the file into place here, so we have to grab the
            # filename_lock again.  We acquire the lock no matter what
            # since we remove the file in the middle.
            try:
                filename_lock.acquire()
                if (filename == None):
                    filename = os.path.join(cachedir, info["filename"])
                    filename = self.nextFreeFilename (filename)
                try:
                    os.remove (filename)
                except:
                    pass
                try:
                    os.move (tmp_filename, filename)
                except:
                    filename = None
            finally:
                filename_lock.release()
    
            try:
                if (db_write_lock):
                    db_write_lock.acquire()
    
                self.filename = filename
                self.etag = info["etag"]
                self.modified = info["modified"]
                self.url = url
                self.updated = True
            finally:
                if (db_write_lock):
                    db_write_lock.release()
        finally:
            self.lock.release()
