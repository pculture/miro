#!/bin/bash

# This script installs dependencies for building and running Miro on
# Fedora 16.
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run as root.

# Last updated:    2013-02-05
# Last updated by: Hans Ulrich Niedermann

yum groupinstall "Development Tools" "Development Libraries"

yum install \
   ffmpeg-devel \
   avahi-compat-libdns_sd \
   Pyrex \
   python-devel \
   pygtk2-devel \
   gtk2-devel \
   pygtk2 \
   pygobject2 \
   gtk2 \
   gnome-python2-gconf \
   dbus-python \
   rb_libtorrent \
   rb_libtorrent-python \
   webkitgtk-devel \
   pywebkitgtk \
   gstreamer-python \
   python-mutagen \
   boost-devel \
   sqlite-devel \
   taglib-devel \
   zlib-devel \
   ffmpeg
