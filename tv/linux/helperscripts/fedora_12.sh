#!/bin/bash

# This script installs dependencies for building and running Miro on
# Fedora 12.
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run as root.

# Last updated:    4/15/2010
# Last updated by: Will Kahn-Greene

yum groupinstall "Development Tools" "Development Libraries"

yum install \
   Pyrex \
   gecko-devel-unstable \
   pygtk2-devel \
   rb_libtorrent \
   rb_libtorrent-python \
   pywebkitgtk \
   ffmpeg \
   ffmpeg2theora
