#/bin/bash
# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

set -o errexit
set -x

# =============================================================================

./setup_binarykit.sh
BKIT_VERSION="$(cat binary_kit_version)"

# =============================================================================

OS_VERSION=$(uname -r | cut -d . -f 1)
if [[ $OS_VERSION == "10" ]] || [[ $OS_VERSION == "11" ]]; then
    TARGET_OS_VERSION=10.6
else
    echo "## This script can only be used under Mac OS X 10.6 and 10.7."
    exit 1
fi

# =============================================================================

PYTHON_VERSION=2.7
SDK_ROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer
SDK_DIR="$SDK_ROOT/SDKs/MacOSX$TARGET_OS_VERSION.sdk"

if [[ ! -e $SDK_DIR ]]; then
    echo "You don't seem to have XCode 4 installed."
    exit 1
fi

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

tar -zxf $BKIT_DIR/Python-2.7.3.tgz
cd $WORK_DIR/Python-2.7.3

patch -p0 < $BKIT_DIR/patches/Python-2.7.2/setup.py.patch
patch -p0 < $BKIT_DIR/patches/Python-2.7.2/Makefile.pre.in.patch

./configure --prefix=$SBOX_DIR \
            --enable-framework=$SBOX_DIR/Frameworks \
            --enable-universalsdk=$SDK_DIR \
            --with-universal-archs=intel

make frameworkinstall

PYTHON_ROOT=$SBOX_DIR/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python
PYTHON_SITE_DIR=$PYTHON_ROOT/lib/python$PYTHON_VERSION/site-packages

SDK_FLAGS="-isysroot $SDK_DIR"

# libcurl =====================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/curl-7.25.0.tar.gz
cd $WORK_DIR/curl-7.25.0


# generate 32 bit file
export CFLAGS="-arch i386 $SDK_FLAGS"
export LDFLAGS=$CFLAGS
./configure --disable-dependency-tracking --with-ssl=/usr --prefix=$SBOX_DIR
cp include/curl/curlbuild.h include/curl/curlbuild32.h

# generate 64-bit file
export CFLAGS="-arch x86_64 $SDK_FLAGS"
export LDFLAGS=$CFLAGS
./configure --disable-dependency-tracking --with-ssl=/usr --prefix=$SBOX_DIR
cp include/curl/curlbuild.h include/curl/curlbuild64.h

# Everybody can use these now
export CFLAGS="-arch i386 -arch x86_64 $SDK_FLAGS"
export LDFLAGS=$CFLAGS
./configure --disable-dependency-tracking --with-ssl=/usr --prefix=$SBOX_DIR

cat > include/curl/curlbuild.h << EOF
#if defined(__LP64__)
#include "curlbuild64.h"
#else
#include "curlbuild32.h"
#endif
EOF

make install
install -m644 include/curl/curlbuild64.h $SBOX_DIR/include
install -m644 include/curl/curlbuild32.h $SBOX_DIR/include

# pycurl ======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/pycurl-7.19.0.tar.gz
cd $WORK_DIR/pycurl-7.19.0

$PYTHON setup.py build --curl-config=$SBOX_DIR/bin/curl-config
$PYTHON setup.py install

# PyObjC and friends, Pyrex =========================================

for pkg in "distribute-0.6.4" \
           "altgraph-0.9" \
           "macholib-1.4.3" \
           "mutagen-1.20" \
           "modulegraph-0.9.1" \
           "py2app-0.6.3" \
           "Pyrex-0.9.9"
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

cd $WORK_DIR
tar -zxf $BKIT_DIR/pyobjc-32.tar.gz

cd $WORK_DIR/pyobjc-32/pyobjc/pyobjc-core
for patch_file in $BKIT_DIR/patches/pyobjc-core-2.2/*.patch; do
    patch -p0 < $patch_file
done

cd $WORK_DIR/pyobjc-32/pyobjc/pyobjc-framework-Cocoa
for p in $BKIT_DIR/patches/pyobjc-framework-Cocoa-2.2/*.patch; do
    patch -p0 < $p
done

cd $WORK_DIR/pyobjc-32/pyobjc/pyobjc-framework-Quartz
for p in $BKIT_DIR/patches/pyobjc-framework-Quartz-2.2/*.patch; do
    patch -p0 < $p
done

# Apple patches
cd $WORK_DIR/pyobjc-32/pyobjc

# Note: Not needed: these have already been patched in the sources given.
#for patch in "parser-fixes.diff" \
#             "float.diff" \
#             "CGFloat.diff" \
#             "pyobjc-core_Modules_objc_selector.m.diff"
#do
#    patch -p0 < ../patches/$patch
#done

ed - pyobjc-framework-Cocoa/Lib/Foundation/PyObjC.bridgesupport < ../patches/pyobjc-framework-Cocoa_Lib_Foundation_PyObjC.bridgesupport.ed
ed - pyobjc-framework-Cocoa/Lib/PyObjCTools/Conversion.py < ../patches/pyobjc-framework-Cocoa_Lib_PyObjCTools_Conversion.py.ed

# Don't know why the install target for the pyobjc-core must be run twice
# for files to install properly.  Oh well whatever works...
for pkg in "pyobjc-core" \
           "pyobjc-core" \
           "pyobjc-framework-Cocoa" \
           "pyobjc-framework-ExceptionHandling" \
           "pyobjc-framework-LaunchServices" \
           "pyobjc-framework-Quartz" \
           "pyobjc-framework-QTKit" \
           "pyobjc-framework-ScriptingBridge" \
           "pyobjc-framework-WebKit" \
          "pyobjc-framework-FSEvents"
do
    cd $WORK_DIR/pyobjc-32/pyobjc/$pkg

    if [[ -e setup.cfg ]]; then
        echo "[easy_install]" >> setup.cfg
        echo "zip_ok = 0" >> setup.cfg
    fi

    $PYTHON setup.py install
done


# boost sources + bjam ========================================================

cd $WORK_DIR

BOOST_VERSION=1_49_0
BOOST_VERSION_FULL=1_49_0

tar -xzf $BKIT_DIR/boost_$BOOST_VERSION_FULL.tar.gz
cd boost_$BOOST_VERSION_FULL

cd tools/build/v2/engine
./build.sh
cd `find . -type d -maxdepth 1 | grep bin.`
mkdir -p $SBOX_DIR/bin
cp bjam $SBOX_DIR/bin

export BOOST_ROOT=$WORK_DIR/boost_$BOOST_VERSION_FULL

# libtorrent ==================================================================

cd $WORK_DIR
DARWIN_CONFIG=`find $BOOST_ROOT -name darwin.jam`
perl -pi -e "s|root.*\?=.*|root = $SDK_ROOT ;|" $DARWIN_CONFIG

USER_CONFIG=`find $BOOST_ROOT -name user-config.jam`
echo "using python : : $PYTHON_ROOT/bin/python$PYTHON_VERSION ;" >> $USER_CONFIG

tar -xvf $BKIT_DIR/libtorrent-rasterbar-*
pushd libtorrent-rasterbar-*
patch -p1 < $BKIT_DIR/patches/libtorrent-rasterbar-0.15.5/libtorrent-boost-filesystem-version.patch
popd
cd libtorrent-rasterbar-*/bindings/python
$SBOX_DIR/bin/bjam dht-support=on \
                   toolset=darwin \
                   macosx-version=$TARGET_OS_VERSION \
                   architecture=x86 \
                   address-model=32_64 \
                   boost=source \
                   boost-link=static \
                   release

LIBTORRENT_MODULE=$(find bin -name libtorrent.so)
cp $LIBTORRENT_MODULE $PYTHON_SITE_DIR

# =============================================================================

echo "Done."
