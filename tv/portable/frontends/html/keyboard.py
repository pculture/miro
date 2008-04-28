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

"""Keyboard controls that don't map to menu items.  Right now this is just
arrow keys, but it should be pretty easy to extend.
"""

from miro import app
from miro import eventloop
from miro import tabs

UP = 1
DOWN = 2
LEFT = 3
RIGHT = 4
SPACE = 5
ESCAPE = 6
UNSUPPORTED = -1

@eventloop.asUrgent
def handleKey(key, shiftDown, controlDown):
    if app.htmlapp.playbackController.currentItem is None:
        handleKeyNoPlayback(key, shiftDown, controlDown)
    else:
        handleKeyPlayback(key, shiftDown, controlDown)

def handleKeyNoPlayback(key, shiftDown, controlDown):
    if key not in (UP, DOWN, SPACE):
        return
    if app.selection.tabListActive:
        selectionArea = app.selection.tabListSelection
        iterator = tabs.tabIterator()
        area = 'tablist'
    else:
        selectionArea = app.selection.itemListSelection
        if selectionArea.currentView is None:
            return
        iterator = selectionArea.currentView
        area = 'itemlist'
    if key == UP:
        toSelect = selectionArea.firstBeforeSelection(iterator)
    elif key == DOWN:
        toSelect = selectionArea.firstAfterSelection(iterator)
    elif key == SPACE:
        toSelect = None
        app.htmlapp.playbackController.playPause()
    if toSelect is not None:
        if app.selection.tabListActive:
            itemView = tabs.getViewForTab(toSelect)
        else:
            itemView = selectionArea.currentView
        app.selection.selectItem(area, itemView, toSelect.getID(),
                shiftDown, controlDown)

def handleKeyPlayback(key, shiftDown, controlDown):
    if key == RIGHT:
        if controlDown:
            app.htmlapp.playbackController.skip(1)
        else:
            def rightKeyTimeCallback(time):
                if time is not None:
                    app.htmlapp.videoDisplay.getDuration(lambda d: rightKeyDurationCallback(time, d))
            def rightKeyDurationCallback(time, duration):
                time += 30.0
                if time < duration:
                    app.htmlapp.videoDisplay.setCurrentTime(time)
            app.htmlapp.videoDisplay.getCurrentTime(rightKeyTimeCallback)
    elif key == LEFT:
        if controlDown:
            app.htmlapp.playbackController.skip(-1)
        else:
            def leftKeyTimeCallback(time):
                if time is not None:
                    time -= 10.0
                    if time > 0.0:
                        app.htmlapp.videoDisplay.setCurrentTime(time)
            app.htmlapp.videoDisplay.getCurrentTime(leftKeyTimeCallback)
    elif key == UP:
        app.htmlapp.videoDisplay.getVolume(lambda v: app.htmlapp.videoDisplay.setVolume(v + 0.05))
    elif key == DOWN:
        app.htmlapp.videoDisplay.getVolume(lambda v: app.htmlapp.videoDisplay.setVolume(v - 0.05))
    elif key == SPACE:
        app.htmlapp.playbackController.playPause()
    elif key == ESCAPE:
        app.htmlapp.videoDisplay.exitFullScreen()
