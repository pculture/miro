#!/usr/bin/env python

"""
This script looks through the XML files next to it, and re-downloads the icons
for the search engines.
"""
from cStringIO import StringIO
import operator
import os
import struct
from xml.dom.minidom import parse
import urllib2
import urlparse

import BeautifulSoup
from PIL import BmpImagePlugin, PngImagePlugin, Image

THIS_DIRECTORY = os.path.dirname(__file__) or '.'
ICON_TEMPLATE = os.path.join(THIS_DIRECTORY, '..', 'images',
                              'search_icon_%s.png')


# copied from http://djangosnippets.org/snippets/1287/
def load_icon(file, index=None):
    '''
    Load Windows ICO image.

    See http://en.wikipedia.org/w/index.php?oldid=264332061 for file format
    description.
    '''
    if isinstance(file, basestring):
        file = open(file, 'rb')

    header = struct.unpack('<3H', file.read(6))

    # Check magic
    if header[:2] != (0, 1):
        raise SyntaxError('Not an ICO file')

    # Collect icon directories
    directories = []
    for i in xrange(header[2]):
        directory = list(struct.unpack('<4B2H2I', file.read(16)))
        for j in xrange(3):
            if not directory[j]:
                directory[j] = 256

        directories.append(directory)

    if index is None:
        # Select best icon
        directory = max(directories, key=operator.itemgetter(slice(0, 3)))
    else:
        directory = directories[index]

    # Seek to the bitmap data
    file.seek(directory[7])

    prefix = file.read(16)
    file.seek(-16, 1)

    if PngImagePlugin._accept(prefix):
        # Windows Vista icon with PNG inside
        image = PngImagePlugin.PngImageFile(file)
    else:
        # Load XOR bitmap
        image = BmpImagePlugin.DibImageFile(file)
        if image.mode == 'RGBA':
            # Windows XP 32-bit color depth icon without AND bitmap
            pass
        else:
            # Patch up the bitmap height
            image.size = image.size[0], image.size[1] >> 1
            d, e, o, a = image.tile[0]
            image.tile[0] = d, (0, 0) + image.size, o, a

            # Calculate AND bitmap dimensions. See
            # http://en.wikipedia.org/w/index.php?oldid=264236948#Pixel_storage
            # for description
            offset = o + a[1] * image.size[1]
            stride = ((image.size[0] + 31) >> 5) << 2
            size = stride * image.size[1]

            # Load AND bitmap
            file.seek(offset)
            string = file.read(size)
            mask = Image.fromstring('1', image.size, string, 'raw',
                                    ('1;I', stride, -1))

            image = image.convert('RGBA')
            image.putalpha(mask)

    return image

def get_favicon_url(url):
    parsed_url = urlparse.urlparse(url)
    root = '%s://%s/' % (
            parsed_url.scheme,
            parsed_url.netloc)
    data = urllib2.urlopen(root).read()
    bs = BeautifulSoup.BeautifulSoup(data)
    icons = [i for i in bs.findAll('link') if 'icon' in i['rel'].lower() and
             'apple-' not in i['rel'].lower()]
    if icons:
        return urlparse.urljoin(root, icons[0]['href'])
    parsed_url = urlparse.urlparse(url)
    return '%s://%s/favicon.ico' % (
        parsed_url.scheme,
        parsed_url.netloc)
# roughly copied from tv/lib/searchengines.py
engines = {}

for f in os.listdir(THIS_DIRECTORY):
    if f.endswith('.xml'):
        id_ = url = None
        dom = parse(f)
        for child in dom.documentElement.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                tag = child.tagName
                text = child.childNodes[0].data
                if tag == 'id':
                    id_ = text
                elif tag == 'url':
                    url = text
        if id_ is None or url is None:
            print 'invalid search XML:', f
            continue

        if 'gdata.youtube.com' in url:
            # fix for YouTube URLs
            url = url.replace('gdata.youtube.com', 'www.youtube.com')
        out_file = ICON_TEMPLATE % id_
        favicon_url = get_favicon_url(url)
        print 'getting', favicon_url
        try:
            data = StringIO(urllib2.urlopen(favicon_url).read())
        except urllib2.HTTPError:
            print 'invalid URL', favicon_url
            continue
        image = load_icon(data, 0)
        image = image.resize((16, 16))
        image.save(out_file, optimize=True)
        print 'wrote', out_file
