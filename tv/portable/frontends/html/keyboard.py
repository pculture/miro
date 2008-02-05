# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""Keyboard controls that don't map to menu items.  Right now this is just
arrow keys, but it should be pretty easy to extend.
"""

import app
import eventloop
import tabs

UP = 1
DOWN = 2
LEFT = 3
RIGHT = 4
SPACE = 5
ESCAPE = 6
UNSUPPORTED = -1

@eventloop.asUrgent
def handleKey(key, shiftDown, controlDown):
    if app.controller.playbackController.currentItem is None:
        handleKeyNoPlayback(key, shiftDown, controlDown)
    else:
        handleKeyPlayback(key, shiftDown, controlDown)

def handleKeyNoPlayback(key, shiftDown, controlDown):
    if key not in (UP, DOWN):
        return
    if app.controller.selection.tabListActive:
        selectionArea = app.controller.selection.tabListSelection
        iterator = tabs.tabIterator()
        area = 'tablist'
    else:
        selectionArea = app.controller.selection.itemListSelection
        if selectionArea.currentView is None:
            return
        iterator = selectionArea.currentView
        area = 'itemlist'
    if key == UP:
        toSelect = selectionArea.firstBeforeSelection(iterator)
    else:
        toSelect = selectionArea.firstAfterSelection(iterator)
    if toSelect is not None:
        if app.controller.selection.tabListActive:
            itemView = tabs.getViewForTab(toSelect)
        else:
            itemView = selectionArea.currentView
        app.controller.selection.selectItem(area, itemView, toSelect.getID(),
                shiftDown, controlDown)

def handleKeyPlayback(key, shiftDown, controlDown):
    # We need a value that's not a valid time, volume, or duration and not None
    time = -33
    duration = -33
    volume = -33
    def durationCallback(dur):
        duration = dur
        if volume != -33 and time != -33:
            actualHandleKey()
    def timeCallback(tim):
        time = tim
        if volume != -33 and duration != -33:
            actualHandleKey()
    def volumeCallback(vol):
        volume = vol
        if duration != -33 and time != -33:
            actualHandleKey()
    def actualHandleKey():
        if key == RIGHT:
            if controlDown:
                app.controller.playbackController.skip(1)
            else:
                if time is not None:
                    time += 30.0
                    if time < duration:
                        app.controller.videoDisplay.setCurrentTime(time)
        elif key == LEFT:
            if controlDown:
                app.controller.playbackController.skip(-1)
            else:
                if time is not None:
                    time -= 10.0
                    if time > 0.0:
                        app.controller.videoDisplay.setCurrentTime(time)
        elif key == UP:
            app.controller.videoDisplay.setVolume(volume + 0.05)
        elif key == DOWN:
            app.controller.videoDisplay.setVolume(volume - 0.05)
        elif key == SPACE:
            app.controller.playbackController.playPause()
        elif key == ESCAPE:
            app.controller.videoDisplay.exitFullScreen()
    # When all of the values have been set, we actually handle the key
    app.controller.videoDisplay.getCurrentTime(timeCallback)
    app.controller.videoDisplay.getDuration(durationCallback)
    app.controller.videoDisplay.getVolume(volumeCallback)
