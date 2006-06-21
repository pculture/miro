import item
import os
import threading
import httpclient
from fasttypes import LinkedList
from eventloop import asIdle, addIdle, addTimeout
import config
import prefs
import time

RUNNING_MAX = 3

class IconCacheUpdater:
    def __init__ (self):
        self.idle = LinkedList()
        self.vital = LinkedList()
        self.runningCount = 0
        self.inShutdown = False

    @asIdle
    def requestUpdate (self, item, is_vital = False):
        if is_vital:
            item.dbItem.confirmDBThread()
            if item.filename and os.access (item.filename, os.R_OK):
                is_vital = False
        if self.runningCount < RUNNING_MAX:
            addIdle (item.requestIcon, "Icon Request")
            self.runningCount += 1
        else:
            if is_vital:
                self.vital.prepend(item)
            else:
                self.idle.prepend(item)

    def updateFinished (self):
        if self.inShutdown:
            self.runningCount -= 1
            return

        if len (self.vital) > 0:
            item = self.vital.pop()
        elif len (self.idle) > 0:
            item = self.idle.pop()
        else:
            self.runningCount -= 1
            return
        
        addIdle (item.requestIcon, "Icon Request")

    @asIdle
    def clearVital (self):
        self.vital = LinkedList()

    @asIdle
    def shutdown (self):
        self.inShutdown = True

iconCacheUpdater = IconCacheUpdater()
class IconCache:
    def __init__ (self, dbItem, is_vital = False):
        self.etag = None
        self.modified = None
        self.filename = None
        self.url = None

        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.dbItem = dbItem

        self.requestUpdate (is_vital=is_vital)

    ##
    # Finds a filename that's unused and similar the the file we want
    # to download
    def nextFreeFilename(self, name):
        if not os.access(name,os.F_OK):
            return name
        parts = name.split('.')
        count = 1
        if len(parts) == 1:
            newname = "%s.%s" % (name, count)
            while os.access(newname,os.F_OK):
                count += 1
                newname = "%s.%s" % (name, count)
        else:
            parts[-1:-1] = [str(count)]
            newname = '.'.join(parts)
            while os.access(newname,os.F_OK):
                count += 1
                parts[-2] = str(count)
                newname = '.'.join(parts)
        return newname

    def errorCallback(self, url, error = None):
        self.dbItem.confirmDBThread()

        # Don't clear the cache on an error.
        if self.url != url:
            self.url = url
            self.etag = None
            self.modified = None
            self.dbItem.signalChange()
        self.updating = False
        if self.needsUpdate:
            self.needsUpdate = False
            self.requestUpdate()
        elif error is not None:
            addTimeout(3600,self.requestUpdate, "Thumbnail request for %s" % url)
        else:
            self.updated = True
        iconCacheUpdater.updateFinished ()

    def updateIconCache (self, url, info):
        self.dbItem.confirmDBThread()

        if info == None or (info['status'] != 304 and info['status'] != 200):
            self.errorCallback(url)
            return
        try:
            # Our cache is good.  Hooray!
            if (info['status'] == 304):
                self.updated = True
                return
            # We have to update it, and if we can't write to the file, we
            # should pick a new filename.
            if (self.filename and not os.access (self.filename, os.R_OK | os.W_OK)):
                self.filename = None

            cachedir = config.get(prefs.ICON_CACHE_DIRECTORY)
            try:
                os.makedirs (cachedir)
            except:
                pass

            try:
                # Download to a temp file.
                if (self.filename):
                    tmp_filename = self.filename + ".part"
                else:
                    tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"

                tmp_filename = self.nextFreeFilename (tmp_filename)
                output = file (tmp_filename, 'wb')
                output.write(info["body"])
                output.close()
            except IOError:
                os.remove (tmp_filename)
                return

            if (self.filename == None):
                self.filename = os.path.join(cachedir, info["filename"])
                self.filename = self.nextFreeFilename (self.filename)
            try:
                os.remove (self.filename)
            except:
                pass
            try:
                os.rename (tmp_filename, self.filename)
            except:
                self.filename = None
        
            if (info.has_key ("etag")):
                self.etag = info["etag"]
            else:
                self.etag = None
            if (info.has_key ("modified")):
                self.modified = info["modified"]
            else:
                self.modified = None
            self.url = url
        finally:
            self.dbItem.signalChange()
            self.updating = False
            if self.needsUpdate:
                self.needsUpdate = False
                self.requestUpdate()
            iconCacheUpdater.updateFinished ()

    def requestIcon (self):
        self.dbItem.confirmDBThread()
        if (self.updating):
            self.needsUpdate = True
            iconCacheUpdater.updateFinished ()
            return
        try:
            url = self.dbItem.getThumbnailURL()
        except:
            url = self.url

        # Only verify each icon once per run unless the url changes
        if (self.updated and url == self.url):
            iconCacheUpdater.updateFinished ()
            return

        self.updating = True

        if url is None or url.startswith("file://") or url.startswith("/"):
            self.errorCallback(url)
            return

        if (url == self.url and self.filename and os.access (self.filename, os.R_OK)):
            httpclient.grabURL (url, lambda(info):self.updateIconCache(url, info), lambda(error):self.errorCallback(url, error), etag=self.etag, modified=self.modified)
        else:
            httpclient.grabURL (url, lambda(info):self.updateIconCache(url, info), lambda(error):self.errorCallback(url, error))

    def requestUpdate (self, is_vital = False):
        if hasattr (self, "updating") and hasattr (self, "dbItem"):
            iconCacheUpdater.requestUpdate (self, is_vital = is_vital)

    def onRestore(self):
        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.requestUpdate ()

    def isValid(self):
        self.dbItem.confirmDBThread()
        return self.filename is not None and os.path.exists(self.filename)

    def getFilename(self):
        self.dbItem.confirmDBThread()
        if self.url and self.url.startswith ("file://"):
            return self.url[len("file://"):]
        elif self.url and self.url.startswith ("/"):
            return self.url
        else:
            return self.filename
