#!/usr/bin/python

# test.py -- test the FixedListStore python wrapper

import sys
import os
import shutil
import subprocess
import time
import itertools

import gobject
import gtk

for dirname in ("build", "dist"):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
subprocess.check_call(["python",  "test-setup.py", "install", "--prefix", "dist"])
#subprocess.check_call(["touch", "build/lib.linux-x86_64-2.7/miro/__init__.py"])
sys.path.append("dist/lib/python2.7/site-packages/")

print 'running...'
print

import fixedliststore

rows = 100
columns = 10
treeview = gtk.TreeView()
cell = gtk.CellRendererText()

def celldatafunction(column, cell, model, it, col_num):
    row = model.row_of_iter(it)
    text = "cell %s %s" % (row, col_num)
    cell.set_property("text", text)

for i in range(columns):
    col = gtk.TreeViewColumn('Column %s' % i)
    treeview.append_column(col)
    col.pack_start(cell, True)
    col.set_cell_data_func(cell, celldatafunction, i)

model = fixedliststore.FixedListStore(rows)
treeview.set_model(model)

def on_click(b):
    start = time.time()
    treeview.queue_draw()
    while gtk.events_pending():
        gtk.main_iteration()
    end = time.time()
    print 'redraw in %0.3f seconds' % (end-start)

button = gtk.Button("Push me")
button.connect("clicked", on_click)


scroller = gtk.ScrolledWindow()
scroller.add(treeview)

vbox = gtk.VBox()
vbox.pack_start(button, False)
vbox.pack_start(scroller)

window = gtk.Window()
window.add(vbox)
window.set_size_request(800, 500)
window.show_all()
window.connect("destroy", lambda w: gtk.main_quit())
gtk.main()

print '...done'
