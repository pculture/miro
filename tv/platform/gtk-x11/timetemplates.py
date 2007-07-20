#!/usr/bin/env python2.4

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

import os
import sys

PREFIX = '/usr'
os.environ['PREFIX'] = PREFIX
os.environ['MIRO_SHARE_ROOT'] = 'dist/%s/share/' % PREFIX
os.environ['MIRO_RESOURCE_ROOT'] = 'dist/usr/share/miro/resources/'
rv = os.system('python2.4 setup.py install --root=./dist --prefix=$PREFIX')
if rv != 0:
    print "FAILURE BUILDING MIRO"
    sys.exit()
sys.path.insert(0, 'dist/%s/lib/python2.4/site-packages/miro' % PREFIX)
import app

# OK miro environment is set up.
import tempfile
from xml import sax
from StringIO import StringIO
from time import time

import item
import feed
import database
import storedatabase
import template
import template_compiler
from template import Handle, fillAttr, quoteAndFillAttr
from IOBuffer import IOBuffer
from xhtmltools import urlencode
from templatehelper import quoteattr, escape, toUni
from string import Template
import app
import sorts
import indexes
import filters

resourcePath = 'dist/%s/share/miro/resources/' % PREFIX
template_compiler.setResourcePath('file://' + os.path.abspath(resourcePath))

class FakeView:
    def map(*args, **kwargs):
        pass

domHandler = "FAKEDOMHANDLER"
dtvPlatform = "gtk"
eventCookie = "oreo"

def getSubtemplateRenderFunc(filename, obj):
    fd, temppath = tempfile.mkstemp()
    viewName = 'arbitraryView'
    fout = os.fdopen(fd, 'wt')
    fout.write("""\
<span t:repeatForView="%s">
    <t:includeTemplate filename="%s" />
</span>""" % (viewName, filename))
    fout.close()
    handle = template_compiler.MetaHandle()

    tcc = template_compiler.TemplateContentCompiler(handle, viewName)
    p = sax.make_parser()
    p.setFeature(sax.handler.feature_external_ges, False)
    p.setContentHandler(tcc)
    p.parse(temppath)
    os.unlink(temppath)

    global domHandler, dtvPlatform, eventCookie, arbitraryView
    arbitraryView = FakeView()

    fileobj = StringIO()
    fileobj.write("class Foo:")
    tcc.handle.render(fileobj)
    fileobj.write('\n\n    out = IOBuffer()\n')
    for count in range(len(tcc.outputLists[0])):
        (func, args) = tcc.outputLists[0][count]
        fileobj.write(func('out','','    ',args))
    fileobj.write('    out.close()\n')        
    fileobj.write('    rep_0_handle = staticmethod(rep_0_handle)\n')
    if 0: # change to if 1 to debug the template output
        i = 2
        for line in fileobj.getvalue().split("\n"):
            print '%s: %s' % (i, line)
            i += 1
    exec fileobj.getvalue()
    return Foo.rep_0_handle

def timeIt(name, func, repeat):
    start = time()
    for x in xrange(repeat):
        func()
        if x % 100 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
    print
    totalTime = time() - start
    fps = repeat / totalTime
    print "%s: %s fills in %.2f seconds (%.2f fills/second)" % \
            (name, repeat, totalTime, fps)

def timeDownloadedItem():
    f = feed.Feed('dtv:manualFeed')
    class FakeEntry:
        def __init__(self):
            self.__dict__ = {
                'title': 'foo', 
                'enclosures' : {},
            }
        def __getitem__(self, key):
            return self.__dict__[key]

    i = item.Item(FakeEntry(), feed_id=f.getID())
    func = getSubtemplateRenderFunc('download-item', i)
    def render():
        func(i, 'arbitraryView', "arbitrary-tid")
    timeIt('download-item', render, 10000)

def timeChannel():
    db = database.defaultDatabase
    db.liveStorage = storedatabase.LiveStorage()
    rocketboom = None
    for obj, dummy in db.objects:
        if isinstance(obj, feed.Feed) and 'rocketboom' in obj.getTitle().lower():
            rocketboom = obj
            break
    assert rocketboom is not None
    class DummyObject:
        pass
    app.controller = DummyObject()
    app.controller.selection.currentTab = DummyObject()
    app.controller.selection.currentTab.obj = rocketboom
    def render():
        template.fillTemplate('channel', domHandler, dtvPlatform, eventCookie)
    timeIt('channel', render, 1000)

tests = {
  'download-item' : timeDownloadedItem,
  'channel' : timeChannel,
}

if len(sys.argv) < 2:
    todo = tests.values()
else:
    todo = [tests[i] for i in sys.argv[1:]]
for test in todo:
    test()
