import item
import os
import threading
from download_utils import grabURLAsync
from fasttypes import LinkedList
from eventloop import asIdle, addIdle
import config
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
            item.dbItem.beginRead()
            try:
                if item.filename and os.access (item.filename, os.R_OK):
                    is_vital = False
            finally:
                item.dbItem.endRead()
        if self.runningCount < RUNNING_MAX:
            addIdle (item.requestIcon)
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

        addIdle (item.requestIcon)

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

    def updateIconCache (self, info, url):
        self.dbItem.beginChange()
        try:
            try:
                # Error during download, or no url.  To reflect that,
                # clear the cache if there was one before.
                if (info == None):
                    try:
                        if (self.filename):
                            os.remove (self.filename)
                    except:
                        pass
                    self.url = url
                    self.filename = None
                    self.etag = None
                    self.modified = None
                    return
    
                # Our cache is good.  Hooray!
                if (info['status'] == 304):
                    self.updated = True
                    return
            
                # We have to update it, and if we can't write to the file, we
                # should pick a new filename.
                if (self.filename and not os.access (self.filename, os.R_OK | os.W_OK)):
                    self.filename = None
    
                cachedir = config.get(config.ICON_CACHE_DIRECTORY)
                try:
                    os.makedirs (cachedir)
                except:
                    pass

                # Download to a temp file.
                if (self.filename):
                    tmp_filename = self.filename + ".part"
                else:
                    tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"
    
                tmp_filename = self.nextFreeFilename (tmp_filename)
                output = file (tmp_filename, 'wb')
                output.write(info["body"])
                output.close()
    
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
                #two separate finally sections in case something here throws an exception.
                self.updating = False
                if self.needsUpdate:
                    self.needsUpdate = False
                    self.requestUpdate()
                iconCacheUpdater.updateFinished ()
        finally:
            self.dbItem.endChange()
        

    def requestIcon (self):
        self.dbItem.beginRead()
        try:
            if (self.updating):
                self.needsUpdate = True
                return
            try:
                url = self.dbItem.getThumbnailURL()
            except:
                url = old_url

            # Only verify each icon once per run unless the url changes
            if (self.updated and url == self.url):
                return

            self.updating = True

            if url is None or url.startswith("file://"):
                self.updateIconCache(None, url)
                return

            if (url == self.url and self.filename and os.access (self.filename, os.R_OK)):
                grabURLAsync (self.updateIconCache, url, etag=self.etag, modified=self.modified, args=(url,))
            else:
                grabURLAsync (self.updateIconCache, url, args=(url,))
        finally:
            self.dbItem.endRead()

    def requestUpdate (self, is_vital = False):
        if hasattr (self, "updating") and hasattr (self, "dbItem"):
            iconCacheUpdater.requestUpdate (self, is_vital = is_vital)

    def onRestore(self):
        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.requestUpdate ()

    def isValid(self):
        self.dbItem.beginRead()
        try:
            return self.filename is not None and os.path.exists(self.filename)
        finally:
            self.dbItem.endRead()

    def getFilename(self):
        if self.url and self.url.startswith ("file://"):
            return self.url[len("file://"):]
        else:
            return self.filename
