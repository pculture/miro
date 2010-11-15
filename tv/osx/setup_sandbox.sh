#/bin/bash
# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.


# =============================================================================

./setup_binarykit.sh
BKIT_VERSION="$(cat binary_kit_version)"

# =============================================================================

OS_VERSION=$(uname -r | cut -d . -f 1)
if [[ $OS_VERSION == "9" ]] || [[ $OS_VERSION == "10" ]]; then
    TARGET_OS_VERSION=10.5
else
    echo "## This script can only be used under Mac OS X 10.5 and 10.6."
    exit 1
fi

# =============================================================================

PYTHON_VERSION=2.6
SDK_DIR="/Developer/SDKs/MacOSX$TARGET_OS_VERSION.sdk"

ROOT_DIR=$(pushd ../../ >/dev/null; pwd; popd >/dev/null)
BKIT_DIR=$(pwd)/miro-binary-kit-osx-$BKIT_VERSION/sandbox
SBOX_DIR=$ROOT_DIR/sandbox_$BKIT_VERSION
WORK_DIR=$SBOX_DIR/pkg

PATH=/bin:/sbin:/usr/bin:/usr/sbin:$SBOX_DIR
MACOSX_DEPLOYMENT_TARGET=$TARGET_OS_VERSION

export PATH
export MACOSX_DEPLOYMENT_TARGET

if [[ -e $SBOX_DIR ]]; then
    echo "!! Deleting existing sandbox!"
    rm -rf $SBOX_DIR
fi

# =============================================================================

echo "** Building Miro sandbox..."

mkdir $SBOX_DIR
mkdir $WORK_DIR

# Python ======================================================================

cd $WORK_DIR

tar -zxf $BKIT_DIR/Python-2.6.5.tgz
cd $WORK_DIR/Python-2.6.5

./configure --prefix=$SBOX_DIR \
            --enable-framework=$SBOX_DIR/Frameworks \
            --enable-universalsdk=$SDK_DIR \
            --with-universal-archs=32-bit

patch -p0 < $BKIT_DIR/patches/Python-2.6.5/setup.py.patch
make frameworkinstall

PYTHON_ROOT=$SBOX_DIR/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python
PYTHON_SITE_DIR=$PYTHON_ROOT/lib/python$PYTHON_VERSION/site-packages

export CFLAGS="`$SBOX_DIR/bin/python-config --cflags`"
export LDFLAGS=$CFLAGS

# libcurl =====================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/curl-7.20.1.tar.gz
cd $WORK_DIR/curl-7.20.1

./configure --disable-dependency-tracking --with-ssl=/usr --prefix=$SBOX_DIR
make install

# pycurl ======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/pycurl-7.19.0.tar.gz
cd $WORK_DIR/pycurl-7.19.0

$PYTHON setup.py build --curl-config=$SBOX_DIR/bin/curl-config
$PYTHON setup.py install

# PyObjC and friends, Pyrex and Psyco =========================================

for pkg in "setuptools-0.6c11" \
           "pyobjc-core-2.2" \
           "pyobjc-framework-Cocoa-2.2" \
           "pyobjc-framework-ExceptionHandling-2.2" \
           "pyobjc-framework-LaunchServices-2.2" \
           "pyobjc-framework-QTKit-2.2" \
           "pyobjc-framework-Quartz-2.2" \
           "pyobjc-framework-ScriptingBridge-2.2" \
           "pyobjc-framework-WebKit-2.2" \
           "pyobjc-framework-FSEvents-2.2" \
           "altgraph-0.6.7" \
           "macholib-1.2.1" \
           "modulegraph-0.7.3" \
           "py2app-0.4.3" \
           "Pyrex-0.9.9" \
           "psyco-1.6"
do
    cd $WORK_DIR
    if [[ ! -e $BKIT_DIR/$pkg.tar.gz ]]; then
        echo "$pkg.tar.gz isn't in the binary kit.  aborting..."
        exit 1
    fi

    tar -zxf $BKIT_DIR/$pkg.tar.gz
    cd $WORK_DIR/$pkg
    
    if [[ -e setup.cfg ]]; then
        echo "[easy_install]" >> setup.cfg
        echo "zip_ok = 0" >> setup.cfg
    fi
    
    if [[ -e $BKIT_DIR/patches/$pkg ]]; then
        for patch_file in $BKIT_DIR/patches/$pkg/*.patch; do
            patch -p0 < $patch_file
        done
    fi
    
    $PYTHON setup.py install
done

# boost sources + bjam ========================================================

cd $WORK_DIR

BOOST_VERSION=1_43
BOOST_VERSION_FULL=1_43_0

tar -xzf $BKIT_DIR/boost_$BOOST_VERSION_FULL.tar.gz
cd boost_$BOOST_VERSION_FULL

cd tools/jam/src
./build.sh
cd `find . -type d -maxdepth 1 | grep bin.`
mkdir -p $SBOX_DIR/bin
cp bjam $SBOX_DIR/bin

export BOOST_ROOT=$WORK_DIR/boost_$BOOST_VERSION_FULL

# libtorrent ==================================================================

cd $WORK_DIR

USER_CONFIG=`find $BOOST_ROOT -name user-config.jam`
echo "using python : : $PYTHON_ROOT/bin/python$PYTHON_VERSION ;" >> $USER_CONFIG

tar -xvf $BKIT_DIR/libtorrent-rasterbar-*
cd libtorrent-rasterbar-*/bindings/python

$SBOX_DIR/bin/bjam dht-support=on \
                   toolset=darwin \
                   macosx-version=$TARGET_OS_VERSION \
                   architecture=combined \
                   boost=source \
                   boost-link=static \
                   release

LIBTORRENT_MODULE=$(find bin -name libtorrent.so)
cp $LIBTORRENT_MODULE $PYTHON_SITE_DIR

# =============================================================================

echo "Done."
