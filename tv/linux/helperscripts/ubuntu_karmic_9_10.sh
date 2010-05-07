#!/bin/bash

# This script installs dependencies for building and running Miro on
# Ubuntu 9.10 (Karmic Koala).
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run with sudo.

# Last updated:    5/5/2010
# Last updated by: Will Kahn-Greene

aptitude install \
    build-essential \
    git-core \
    pkg-config \
    python-pyrex \
    python-gtk2-dev

aptitude install \
    libtorrent-rasterbar5 \
    python-libtorrent \
    libwebkit-1.0-2 \
    python-webkit \
    python-gst0.10 \
    python-gconf \
    gstreamer0.10-ffmpeg \
    gstreamer0.10-plugins-base \
    gstreamer0.10-plugins-good \
    gstreamer0.10-plugins-bad \
    gstreamer0.10-plugins-ugly \
    ffmpeg \
    ffmpeg2theora
