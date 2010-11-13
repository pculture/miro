#!/bin/bash

# This script installs dependencies for building and running Miro on
# Fedora 14.
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run as root.

# Last updated:    11/13/2010
# Last updated by: Will Kahn-Greene

yum groupinstall "Development Tools" "Development Libraries"

yum install \
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
   pywebkitgtk \
   gstreamer-python \
   ffmpeg \
   ffmpeg2theora
