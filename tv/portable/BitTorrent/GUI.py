# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# written by Matt Chisholm

from __future__ import division

import gtk
import pango
import gobject
import os.path
import threading

from __init__ import image_root, app_name, FAQ_URL

SPACING = 8
WINDOW_TITLE_LENGTH = 128 # do we need this?
WINDOW_WIDTH = 600
MAX_WINDOW_HEIGHT = 600 # BUG: can we get this from the user's screen size?
MAX_WINDOW_WIDTH  = 600 # BUG: can we get this from the user's screen size?
MIN_MULTI_PANE_HEIGHT = 160

BT_TARGET_TYPE = 0
EXTERNAL_TARGET_TYPE = 1

BT_TARGET       = ("application/x-bittorrent", gtk.TARGET_SAME_APP, BT_TARGET_TYPE      )
EXTERNAL_TARGET = ("text/uri-list"           , 0                  , EXTERNAL_TARGET_TYPE)

# a slightly hackish but very reliable way to get OS scrollbar width
sw = gtk.ScrolledWindow()
SCROLLBAR_WIDTH = sw.size_request()[0] - 48
del sw

def align(obj,x,y):
    a = gtk.Alignment(x,y,0,0)
    a.add(obj)
    return a
    
def halign(obj, amt):
    return align(obj,amt,0.5)

def lalign(obj):
    return halign(obj,0)

def ralign(obj):
    return halign(obj,1)

def valign(obj, amt):
    return align(obj,0.5,amt)

factory = gtk.IconFactory()

# these don't seem to be documented anywhere:
# ICON_SIZE_BUTTON        = 20x20
# ICON_SIZE_LARGE_TOOLBAR = 24x24

for n in 'broken finished info pause paused play queued running remove'.split():
    fn = os.path.join(image_root, ("%s.png"%n))

    pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
    
    set = gtk.IconSet(pixbuf)

    factory.add('bt-%s'%n, set)

factory.add_default()

def get_logo(size=32):
    fn = os.path.join(image_root, 'logo', 'bittorrent_%d.png'%size)
    logo = gtk.Image()
    logo.set_from_file(fn)
    return logo

class Size(long):
    """displays size in human-readable format"""
    size_labels = ['','K','M','G','T','P','E','Z','Y']    
    radix = 2**10

    def __new__(cls, value, precision=None):
        self = long.__new__(cls, value)
        return self

    def __init__(self, value, precision=0):
        long.__init__(self, value)
        self.precision = precision

    def __str__(self, precision=None):
        if precision is None:
            precision = self.precision
        value = self
        for unitname in self.size_labels:
            if value < self.radix and precision < self.radix:
                break
            value /= self.radix
            precision /= self.radix
        if unitname and value < 10 and precision < 1:
            return '%.1f %sB' % (value, unitname)
        else:
            return '%.0f %sB' % (value, unitname)


class Rate(Size):
    """displays rate in human-readable format"""
    def __init__(self, value, precision=2**10):
        Size.__init__(self, value, precision)

    def __str__(self, precision=None):
        return '%s/s'% Size.__str__(self, precision=None)


class Duration(float):
    """displays duration in human-readable format"""
    def __str__(value):
        if value > 365 * 24 * 60 * 60:
            return '?'
        elif value >= 172800:
            return '%d days' % (value//86400) # 2 days or longer
        elif value >= 86400:
            return '1 day %d hours' % ((value-86400)//3600) # 1-2 days
        elif value >= 3600:
            return '%d:%02d hours' % (value//3600, (value%3600)//60) # 1 h - 1 day
        elif value >= 60:
            return '%d:%02d minutes' % (value//60, value%60) # 1 minute to 1 hour
        elif value >= 0:
            return '%d seconds' % int(value)
        else:
            return '0 seconds'

class IconButton(gtk.Button):
    def __init__(self, label, iconpath=None, stock=None):
        gtk.Button.__init__(self)

        self.hbox = gtk.HBox(spacing=5)
        
        self.icon = gtk.Image()
        if stock is not None:
            self.icon.set_from_stock(stock, gtk.ICON_SIZE_BUTTON)
        elif iconpath is not None:
            self.icon.set_from_file(iconpath)
        else:
            raise TypeError, "IconButton needs iconpath or stock"
        self.hbox.pack_start(self.icon)

        self.label = gtk.Label(label)
        self.hbox.pack_start(self.label)

        self.add(halign(self.hbox, 0.5))


class Window(gtk.Window):
    def __init__(self, *args):
        apply(gtk.Window.__init__, (self,)+args)
        self.set_icon_from_file(os.path.join(image_root,'bittorrent.ico'))


class HelpWindow(Window):
    def __init__(self, main, helptext):
        Window.__init__(self)
        self.set_title('%s Help'%app_name)
        self.main = main
        self.set_border_width(SPACING)

        self.vbox = gtk.VBox(spacing=SPACING)
        
        self.faq_box = gtk.HBox(spacing=SPACING)
        self.faq_box.pack_start(gtk.Label("Frequently Asked Questions:"), expand=False, fill=False)
        self.faq_url = gtk.Entry()
        self.faq_url.set_text(FAQ_URL)
        self.faq_url.set_editable(False)
        self.faq_box.pack_start(self.faq_url, expand=True, fill=True)
        self.faq_button = gtk.Button('Go')
        self.faq_button.connect('clicked', lambda w: self.main.visit_url(FAQ_URL) )
        self.faq_box.pack_start(self.faq_button, expand=False, fill=False)
        self.vbox.pack_start(self.faq_box, expand=False, fill=False)

        self.cmdline_args = gtk.Label(helptext)

        self.cmdline_sw = ScrolledWindow()
        self.cmdline_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.cmdline_sw.add_with_viewport(self.cmdline_args)

        self.cmdline_sw.set_size_request(self.cmdline_args.size_request()[0]+SCROLLBAR_WIDTH, 200)

        self.vbox.pack_start(self.cmdline_sw)
        
        self.add(self.vbox)

        self.show_all()
        
        if self.main is not None:
            self.connect('destroy', lambda w: self.main.window_closed('help'))
        else:
            self.connect('destroy', lambda w: gtk.main_quit())
            gtk.main()
                        


    def close(self, widget=None):
        self.destroy()    


class ScrolledWindow(gtk.ScrolledWindow):
    def scroll_to_bottom(self):
        child_height = self.child.child.size_request()[1]
        self.scroll_to(0, child_height)
        
    def scroll_by(self, dx=0, dy=0):
        v = self.get_vadjustment()
        new_y = min(v.upper, v.value + dy)
        self.scroll_to(0, new_y)

    def scroll_to(self, x=0, y=0):
        v = self.get_vadjustment()
        child_height = self.child.child.size_request()[1]
        new_adj = gtk.Adjustment(y, 0, child_height)
        self.set_vadjustment(new_adj)


class AutoScrollingWindow(ScrolledWindow):
    def __init__(self):
        ScrolledWindow.__init__(self)
        self.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                           gtk.DEST_DEFAULT_DROP,
                           [( "application/x-bittorrent",  gtk.TARGET_SAME_APP, BT_TARGET_TYPE )],
                           gtk.gdk.ACTION_MOVE)
        self.connect('drag_motion'       , self.drag_motion       )
#        self.connect('drag_data_received', self.drag_data_received)
        self.vscrolltimeout = None

#    def drag_data_received(self, widget, context, x, y, selection, targetType, time):
#        print 'AutoScrollingWindow.drag_data_received(', widget

    def drag_motion(self, widget, context, x, y, time):
        v = self.get_vadjustment()
        if v.page_size - y <= 10:
            amount = (10 - int(v.page_size - y)) * 2
            self.start_scrolling(amount)
        elif y <= 10:
            amount = (y - 10) * 2
            self.start_scrolling(amount)
        else:
            self.stop_scrolling()

    def scroll_and_wait(self, amount, lock_held):
        if not lock_held:
            gtk.threads_enter()
        self.scroll_by(0, amount)
        if not lock_held:
            gtk.threads_leave()
        if self.vscrolltimeout is not None:
            gobject.source_remove(self.vscrolltimeout)
        self.vscrolltimeout = gobject.timeout_add(100, self.scroll_and_wait, amount, False)
        #print "adding timeout", self.vscrolltimeout, amount

    def start_scrolling(self, amount):
        if self.vscrolltimeout is not None:
            gobject.source_remove(self.vscrolltimeout)            
        self.scroll_and_wait(amount, True)
        
    def stop_scrolling(self):
        if self.vscrolltimeout is not None:
            #print "removing timeout", self.vscrolltimeout
            gobject.source_remove(self.vscrolltimeout)
            self.vscrolltimeout = None

class MessageDialog(gtk.MessageDialog):
    flags = gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT
    
    def __init__(self, parent, title, message,
                 type=gtk.MESSAGE_ERROR,
                 buttons=gtk.BUTTONS_OK,
                 yesfunc=None, nofunc=None,
                 default=None
                 ):
        gtk.MessageDialog.__init__(self, parent,
                                   self.flags,
                                   type, buttons, message)

        self.set_size_request(-1, -1)
        self.set_resizable(gtk.FALSE)
        self.set_title(title)
        if default is not None:
            self.set_default_response(default)
        
        self.label.set_line_wrap(gtk.TRUE)

        self.connect('response', self.callback)

        self.yesfunc = yesfunc
        self.nofunc = nofunc
        self.show_all()

    def callback(self, widget, response_id, *args):
        if ((response_id == gtk.RESPONSE_OK or
             response_id == gtk.RESPONSE_YES) and
            self.yesfunc is not None):
            self.yesfunc()
        if ((response_id == gtk.RESPONSE_CANCEL or
             response_id == gtk.RESPONSE_NO )
            and self.nofunc is not None):
            self.nofunc()
        self.destroy()

class ErrorMessageDialog(MessageDialog):
    flags = gtk.DIALOG_DESTROY_WITH_PARENT


class FileSelection(gtk.FileSelection):

    def __init__(self, main, title='', fullname='', got_location_func=None, no_location_func=None, got_multiple_location_func=None, show=True):
        gtk.FileSelection.__init__(self)
        self.main = main
        self.set_modal(gtk.TRUE)
        self.set_destroy_with_parent(gtk.TRUE)
        self.set_title(title)
        if (got_location_func is None and
            got_multiple_location_func is not None):
            self.set_select_multiple(True)
        self.got_location_func = got_location_func
        self.no_location_func = no_location_func
        self.got_multiple_location_func = got_multiple_location_func
        self.cancel_button.connect("clicked", self.destroy)
        self.d_handle = self.connect('destroy', self.no_location)
        self.ok_button.connect("clicked", self.done)
        self.set_filename(fullname)
        if show:
            self.show()

    def no_location(self, widget=None):
        if self.no_location_func is not None:
            self.no_location_func()

    def done(self, widget=None):
        if self.get_select_multiple():
            self.got_multiple_location()
        else:
            self.got_location()
        self.disconnect(self.d_handle)
        self.destroy()

    def got_location(self):
        if self.got_location_func is not None:
            name = self.get_filename()
            self.got_location_func(name)

    def got_multiple_location(self):
        if self.got_multiple_location_func is not None:
            names = self.get_selections()
            self.got_multiple_location_func(names)
            
    def destroy(self, widget=None):
        gtk.FileSelection.destroy(self)

    def close_child_windows(self):
        self.no_location()

    def close(self, widget=None):
        self.destroy()

class OpenFileSelection(FileSelection):
    pass

class SaveFileSelection(FileSelection):
    pass

class ChooseFolderSelection(FileSelection):
    pass

if os.name == 'nt':
    from venster import comdlg
    class BaseFileSelection:
        _klass = None
        _flags = 0
        _filter = ''
        def __init__(self, main, title='', fullname='',
                     got_location_func=None,
                     no_location_func=None,
                     got_multiple_location_func=None,
                     show=True):
            self.main = main
            self.bfs = self._klass()
            self.bfs.Flags = self._flags
            self.bfs.filter = self._filter

            self.got_location_func = got_location_func
            self.no_location_func  = no_location_func
            self.got_multiple_location_func = got_multiple_location_func
            

            if (got_location_func is None and
                got_multiple_location_func is not None):
                self.bfs.Flags |= comdlg.OFN_ALLOWMULTISELECT

            path, filename = os.path.split(fullname)
            self.bfs.lpstrInitialDir = path
            self.bfs.lpstrFile = filename
            self.bfs.lpstrTitle = title

            self.thread = threading.Thread(target=self.run)
            if show:
                self.show()
            
        def show(self):
            self.thread.start()

        def run(self):
            result = self.bfs.DoModal(parent=self.main.mainwindow.window.handle)
            self.done(result)

        def done(self, result):
            if result is not None:
                if self.got_location_func is not None:
                    self.got_location_func(result)
                elif self.got_multiple_location_func is not None:
                    print result, type(result) # this is broken
                    self.got_multiple_location_func((result,))
            else:
                if self.no_location_func is not None:
                    self.no_location_func()
            

        def close_child_windows(self):
            self.destroy()

        def destroy(self):
            pass

        def close(self):
            self.destroy()
        
    class OpenFileSelection(BaseFileSelection):
        _klass = comdlg.OpenFileDialog
        _flags = comdlg.OFN_FILEMUSTEXIST|comdlg.OFN_PATHMUSTEXIST
        _filter = "Torrent files|*.torrent|All files (*.*)|*.*"

    class SaveFileSelection(BaseFileSelection):
        _klass = comdlg.SaveFileDialog
        _filter = "All files (*.*)|*.*"


class PaddedHSeparator(gtk.VBox):
    def __init__(self, spacing=SPACING):
        gtk.VBox.__init__(self)
        self.sep = gtk.HSeparator()
        self.pack_start(self.sep, expand=False, fill=False, padding=spacing)
        self.show_all()
        

class HSeparatedBox(gtk.VBox):

    def new_separator(self):
        return PaddedHSeparator()

    def _get_children(self):
        return gtk.VBox.get_children(self)

    def get_children(self):
        return self._get_children()[0::2]

    def _reorder_child(self, child, index):
        gtk.VBox.reorder_child(self, child, index)

    def reorder_child(self, child, index):
        children = self._get_children()
        oldindex = children.index(child)
        sep = None
        if oldindex == len(children) - 1:
            sep = children[oldindex-1]
        else:
            sep = children[oldindex+1]

        newindex = index*2
        if newindex == len(children) -1:
            self._reorder_child(sep, newindex-1)
            self._reorder_child(child, newindex)
        else:
            self._reorder_child(child, newindex)
            self._reorder_child(sep, newindex+1)

    def pack_start(self, widget, *args, **kwargs):
        if len(self._get_children()):
            s = self.new_separator()
            gtk.VBox.pack_start(self, s, *args, **kwargs)
            s.show()
        gtk.VBox.pack_start(self, widget, *args, **kwargs)

    def pack_end(self, widget, *args, **kwargs):
        if len(self._get_children()):
            s = self.new_separator()
            gtk.VBox.pack_start(self, s, *args, **kwargs)
            s.show()
        gtk.VBox.pack_end(self, widget, *args, **kwargs)

    def remove(self, widget):
        children = self._get_children()
        if len(children) > 1:
            index = children.index(widget)
            if index == 0:
                sep = children[index+1]
            else:
                sep = children[index-1]
            sep.destroy()
        gtk.VBox.remove(self, widget)
