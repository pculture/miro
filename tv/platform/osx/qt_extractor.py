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


import os
import sys
import glob
import objc
import QTKit
import AppKit
import Foundation

from miro.plat import qtcomp

# =============================================================================

def registerQuicktimeComponents():
    bundlePath = Foundation.NSBundle.mainBundle().bundlePath()
    componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
    components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
    for component in components:
        cmpName = os.path.basename(component)
        if checkComponentCompatibility(cmpName):
            qtcomp.register(component.encode('utf-8'))

def checkComponentCompatibility(name):
    if "Perian" in name or "AC3" in name or "A52" in name:
        if getMajorOSVersion() <= 7:
            return False
    return True

def getMajorOSVersion():
    versionInfo = os.uname()
    versionInfo = versionInfo[2].split('.')
    return int(versionInfo[0])

# =============================================================================

def extractDuration(qtmovie):
    qttime = qtmovie.duration()
    if qttime.timeScale == 0:
        return -1
    return int((qttime.timeValue / float(qttime.timeScale)) * 1000)

# -----------------------------------------------------------------------------

def extractThumbnail(qtmovie, target, width=0, height=0):
    try:
        qttime = qtmovie.duration()
        qttime.timeValue *= .5
        frame = qtmovie.frameImageAtTime_(qttime)
        if frame is objc.nil:
            return "Failure"

        frameSize = frame.size()
        if frameSize.width == 0 or frameSize.height == 0:
            return "Failure"

        if (width == 0) and (height == 0):
            width = frameSize.width
            height = frameSize.height

        frameRatio = frameSize.width / frameSize.height
        sourceSize = frame.size()
        sourceRatio = sourceSize.width / sourceSize.height
        destinationSize = Foundation.NSSize(width, height)
        destinationRatio = destinationSize.width / destinationSize.height

        if sourceRatio > destinationRatio:
            size = Foundation.NSSize(destinationSize.width, destinationSize.width / sourceRatio)
            pos = Foundation.NSPoint(0, (destinationSize.height - size.height) / 2.0)
        else:
            size = Foundation.NSSize(destinationSize.height * sourceRatio, destinationSize.height)
            pos = Foundation.NSPoint((destinationSize.width - size.width) / 2.0, 0)

        destination = AppKit.NSImage.alloc().initWithSize_(destinationSize)
        try:
            destination.lockFocus()
            AppKit.NSGraphicsContext.currentContext().setImageInterpolation_(AppKit.NSImageInterpolationHigh)
            AppKit.NSColor.blackColor().set()
            AppKit.NSRectFill(((0,0), destinationSize))
            frame.drawInRect_fromRect_operation_fraction_((pos, size), ((0,0), sourceSize), AppKit.NSCompositeSourceOver, 1.0)
        finally:
            destination.unlockFocus()

        tiffData = destination.TIFFRepresentation()
        imageRep = AppKit.NSBitmapImageRep.imageRepWithData_(tiffData)
        properties = {AppKit.NSImageCompressionFactor: 0.8}
        jpegData = imageRep.representationUsingType_properties_(AppKit.NSJPEGFileType, properties)
        if jpegData is objc.nil:
            return "Failure"

        jpegData.writeToFile_atomically_(target, objc.YES)
    except Exception, e:
        return "Failure"

    return "Success"

# =============================================================================

moviePath = sys.argv[1].decode('utf-8')
thumbPath = sys.argv[2].decode('utf-8')

info = AppKit.NSBundle.mainBundle().infoDictionary()
info["LSBackgroundOnly"] = "1"
AppKit.NSApplicationLoad()

registerQuicktimeComponents()

(qtmovie, error) = QTKit.QTMovie.movieWithFile_error_(moviePath)
if qtmovie is None or error is not objc.nil:
    sys.exit(0)

duration = extractDuration(qtmovie)
print "Miro-Movie-Data-Length: %s" % duration

thmbResult = extractThumbnail(qtmovie, thumbPath)
print "Miro-Movie-Data-Thumbnail: %s" % thmbResult

sys.exit(0)

# =============================================================================
