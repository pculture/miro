# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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
from objc import YES, NO, nil
from QTKit import *
from AppKit import *
from Foundation import *

from miro.plat import qtcomp
from miro.plat import qttimeutils
from miro.plat.frontends.widgets import mediatypes

def register_quicktime_components():
    bundle_path = os.getenv('MIRO_BUNDLE_PATH')
    if not bundle_path:
        bundle_path = NSBundle.mainBundle().bundlePath().encode('utf-8')
    components_directory_path = os.path.join(bundle_path,
                                             'Contents',
                                             'Components')
    components = glob.glob(os.path.join(components_directory_path,
                                        '*.component'))
    for component in components:
        cmpName = os.path.basename(component)
        stdloc1 = os.path.join("/", "Library", "Quicktime", cmpName)
        stdloc2 = os.path.join("/", "Library", "Audio", "Plug-Ins",
                               "Components", cmpName)
        if not os.path.exists(stdloc1) and not os.path.exists(stdloc2):
            qtcomp.register(component)

def extract_duration(qtmovie):
    try:
        qttime = qtmovie.duration()
        if qttimeutils.qttimescale(qttime) == 0:
            return -1
        return int((qttimeutils.qttimevalue(qttime) /
                   float(qttimeutils.qttimescale(qttime))) * 1000)
    except Exception:
        return -1

def get_type(qtmovie):
    if qtmovie is None:
        return 'other'

    all_tracks = qtmovie.tracks()
    if len(all_tracks) == 0:
        return 'other'

    has_audio = False
    has_video = False
    for track in all_tracks:
        media_type = track.attributeForKey_(QTTrackMediaTypeAttribute)
        if media_type in mediatypes.AUDIO_MEDIA_TYPES:
            has_audio = True
        elif media_type in mediatypes.VIDEO_MEDIA_TYPES:
            has_video = True

    item_type = 'other'
    if has_video:
        item_type = 'video'
    elif has_audio:
        item_type = 'audio'

    return item_type

def extract_thumbnail(qtmovie, target, width=0, height=0):
    try:
        qttime = qtmovie.duration()
        qttime = qttimeutils.qttimevalue_set(qttime,
          int(qttimeutils.qttimevalue(qttime) * 0.5))

        frame = qtmovie.frameImageAtTime_(qttime)
        if frame is nil:
            return False

        frame_size = frame.size()
        if frame_size.width == 0 or frame_size.height == 0:
            return False

        if (width == 0) and (height == 0):
            width = frame_size.width
            height = frame_size.height

        srcsize = frame.size()
        srcratio = srcsize.width / srcsize.height
        destsize = NSSize(width, height)
        destratio = destsize.width / destsize.height

        if srcratio > destratio:
            size = NSSize(destsize.width, destsize.width / srcratio)
            pos = NSPoint(0,
              (destsize.height - size.height) / 2.0)
        else:
            size = NSSize(destsize.height * srcratio, destsize.height)
            pos = NSPoint((destsize.width - size.width) / 2.0, 0)

        dest = NSImage.alloc().initWithSize_(destsize)
        try:
            dest.lockFocus()
            context = NSGraphicsContext.currentContext()
            context.setImageInterpolation_(NSImageInterpolationHigh)
            NSColor.blackColor().set()
            NSRectFill(((0,0), destsize))
            frame.drawInRect_fromRect_operation_fraction_((pos, size),
              ((0,0), srcsize), NSCompositeSourceOver, 1.0)
        finally:
            dest.unlockFocus()

        tiff_data = dest.TIFFRepresentation()
        image_rep = NSBitmapImageRep.imageRepWithData_(tiff_data)
        properties = {NSImageCompressionFactor: 0.8}
        jpeg_data = image_rep.representationUsingType_properties_(
          NSJPEGFileType, properties)
        if jpeg_data is nil:
            return False

        jpeg_data.writeToFile_atomically_(target, YES)
    except Exception:
        return False

    return True

def usage():
    print 'usage: %s movie thumb' % sys.argv[0]

def run(movie_path, thumb_path):
    # XXX movieWithFile_error_ may be asynchronous, but at least when
    # it is done locally it seems to return in such a way that makes it possible
    # to extract stuff.  The QTMovieLoadState attribute never seems to update,
    # maybe because we are missing some Cocoa runloop stuff or something.  One
    # issue arises for streamed movie files (such as some mov), it returns
    # loading state and then we hit failure and Miro puts it into the Misc
    # category despite it actually being playable.
    qtmovie, error = QTMovie.movieWithFile_error_(movie_path, None)
    load_state = QTMovieLoadStateError
    if qtmovie:
        load_state = qtmovie.attributeForKey_(
          QTMovieLoadStateAttribute).longValue()
    if (qtmovie is None or error is not nil or
      load_state < QTMovieLoadStateLoaded):
        return ('other', -1, None)
    
    movie_type = get_type(qtmovie)
    duration = extract_duration(qtmovie)
    thmb_result = False

    if movie_type == "video":
        thmb_result = extract_thumbnail(qtmovie, thumb_path)

    return (movie_type, duration, thmb_result)

def main(argc, argv):
    if argc != 3:
        usage()
        return 1

    movie_path = argv[1]
    thumb_path = argv[2]
    result = run(movie_path, thumb_path)
    print result
    return 0

if __name__ == '__main__':
    info = NSBundle.mainBundle().infoDictionary()
    info["LSBackgroundOnly"] = "1"
    register_quicktime_components()
    sys.exit(main(len(sys.argv), sys.argv))
