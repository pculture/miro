"""Tests for specific database upgrades."""

import tempfile

from miro.test.framework import MiroTestCase
from miro import databaseupgrade
from miro import feed
from miro import item
from miro import folder
from miro import playlist
from miro import storedatabase

class DatabaseUpgradeTest(MiroTestCase):
    def makeSavables(self, *objects):
        return [storedatabase.objectToSavable(o) for o in objects]

    def testUpgrade23(self):
        pl = playlist.SavedPlaylist(u"foo")
        fold = folder.PlaylistFolder(u"bar")
        fd = feed.Feed(u"http://feed.uk")
        it = item.Item({}, feed_id=fd.id)
        container = item.Item({}, feed_id=fd.id)
        container.isContainerItem = True
        fileContainer = item.FileItem('booya', feed_id=fd.id)
        fileContainer.isContainerItem = True
        pl.addItem(it)
        pl.addItem(fileContainer)
        pl.addItem(container)
        pl.setFolder(fold)
        fold.addItem(it)
        pl.addItem(fileContainer)
        fold.addItem(container)
        savables = self.makeSavables(pl, fold, fd, it, container,
                fileContainer)
        changed = databaseupgrade.upgrade(savables, 22, 23)
        self.assertEquals(changed, set(savables[0:2]))
        self.assertEquals(savables[0].savedData['item_ids'], [it.id])
        self.assertEquals(savables[1].savedData['item_ids'], [it.id])
