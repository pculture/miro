#!/bin/bash

# This script installs dependencies for building and running Miro on
# Fedora 13.
#
# You run this sript AT YOUR OWN RISK.  Read through the whole thing
# before running it!
#
# This script must be run as root.

# Last updated:    4/15/2010
# Last updated by: Will Kahn-Greene

yum groupinstall "Developer Tools" "Developer Libraries"

yum install Pyrex gecko-devel-unstable pygtk2-devel

yum install gnome-python2-gtkmozembed rb_libtorrent rb_libtorrent-python
