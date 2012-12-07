#!/bin/bash

# This script installs dependencies for building and running Miro on
# Ubuntu 12.04 (Precise Pangolin).
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run with sudo.

# Last updated:    2012-03-23
# Last updated by: Jesse Johnson

apt-get install \
    build-essential \
    dbus-x11 \
    ffmpeg \
    gstreamer0.10-ffmpeg \
    gstreamer0.10-plugins-bad \
    gstreamer0.10-plugins-base \
    gstreamer0.10-plugins-good \
    gstreamer0.10-plugins-ugly \
    libavahi-compat-libdnssd1 \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libboost-dev \
    libfaac0 \
    libsoup2.4-dev \
    libsqlite3-dev \
    libtag1-dev \
    libtorrent-rasterbar6 \
    libwebkit-dev \
    libwebkitgtk-3.0-0 \
    pkg-config \
    python-appindicator \
    python-gconf \
    python-gst0.10 \
    python-gtk2-dev \
    python-libtorrent \
    python-mutagen \
    python-pycurl \
    python-pyrex \
    python-webkit \
    zlib1g-dev \
