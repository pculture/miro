#/bin/bash
# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
# This script was initially supposed to setup a true isolated sandbox, but 
# unresolved problems remain so it has been modified to install part of the 
# dependencies from prebuilt packages and use some existing system libraries.
# =============================================================================

BKIT_VERSION=20091025

# SANDBOX_VERSION=20071205002

# =============================================================================

echo "Checking binary kit."
BKIT="miro-binary-kit-osx-${BKIT_VERSION}.tar.gz"
BKIT_URL="http://pculture.org/binarykits/${BKIT}"

if [ -d "miro-binary-kit-osx-${BKIT_VERSION}" ]
then
    echo "Binary kit ${BKIT} is already installed.";
else
    echo "Installing ${BKIT}.";
    curl "${BKIT_URL}" > "${BKIT}";
    tar -xzvf "${BKIT}";
    echo "Binary kit ${BKIT} is installed."
fi

PKG_DIR=$(pwd)/miro-binary-kit-osx-$BKIT_VERSION/sandbox

# =============================================================================

if [ $(whoami) != "root" ]; then
    echo "This dependencies setup and installation script must be run as root. Use sudo."
    exit
fi

# =============================================================================

ROOT_DIR=$(pushd ../../../ >/dev/null; pwd; popd >/dev/null)
VERBOSE=no

while getopts ":r:v" option
    do
    case $option in
    r)
        ROOT_DIR=$OPTARG
        ;;
    v)
        VERBOSE=yes
        ;;
    esac
done

# -----------------------------------------------------------------------------

#SANDBOX_DIR=$ROOT_DIR/sandbox
SANDBOX_DIR=/usr/local
WORK_DIR=$SANDBOX_DIR/pkg

# =============================================================================

#SIGNATURE=$SANDBOX_VERSION
#for pkg in $PKG_DIR/*; do
#    SIGNATURE="$SIGNATURE $(basename $pkg) $(stat -f '%z' $pkg)"
#done
#SIGNATURE=$(echo $SIGNATURE | md5)
#SIGNATURE_FILE=$SANDBOX_DIR/signature.md5

# =============================================================================

#setup_required=no
#
#if [ -d $SANDBOX_DIR ]; then
#    echo "Sandbox found, checking signature..."
#
#    if [ -f $SIGNATURE_FILE ]; then
#        local_signature=$(cat -s $SIGNATURE_FILE)
#        if [ $local_signature == $SIGNATURE ]; then
#            echo "Local sandbox is up to date."
#        else
#            echo "Sandbox signature mismatch, setup required."
#            setup_required=yes
#        fi
#    else
#        echo "Unsigned sandbox, setup required."
#        setup_required=yes
#    fi
#    
#    if [ $setup_required == yes ]; then
#        echo "Deleting current sandbox..."
#        rm -rf $SANDBOX_DIR
#    fi
#else
#    old_sandbox="../../../../sandbox"
#    if [ -d $old_sandbox ]; then
#        echo "Sandbox found at deprecated location, setup required."
#        rm -rf $old_sandbox
#    else
#        echo "Sandbox not found, setup required."
#    fi
#    setup_required=yes
#fi
#
#if [ $setup_required == no ]; then
#    exit
#fi

echo "Setting up sandbox in $ROOT_DIR"
mkdir -p $WORK_DIR

# =============================================================================

if [ $VERBOSE == yes ]; then
    OUT=/dev/stdout
else
    OUT=$SANDBOX_DIR/setup.log
    rm -f $OUT
    echo "=== Sandbox setup log - $(date)" >$OUT
fi

# =============================================================================
# Python 2.4.4
# =============================================================================

echo "=== PYTHON 2.4.4 ==============================================================" >>$OUT
echo "Setting up Python 2.4.4"
cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/Python-2.4.4.tgz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/Python-2.4.4
#
#echo ">> Configuring..."
#./configure --prefix=$SANDBOX_DIR \
#            --enable-universalsdk \
#            --enable-framework=$SANDBOX_DIR/Library/Frameworks \
#            --enable-shared \
#            --with-suffix="" \
#            --disable-readline \
#            --disable-tk \
#            --enable-ipv6 \
#             1>>$OUT 2>>$OUT
#
#echo ">> Building & installing..."
#make python.exe 1>>$OUT 2>>$OUT
#make frameworkinstallstructure 1>>$OUT 2>>$OUT
#make bininstall 1>>$OUT 2>>$OUT
#make altbininstall 1>>$OUT 2>>$OUT
#make libinstall 1>>$OUT 2>>$OUT
#make libainstall 1>>$OUT 2>>$OUT
#make inclinstall 1>>$OUT 2>>$OUT
#make sharedinstall 1>>$OUT 2>>$OUT
#make oldsharedinstall 1>>$OUT 2>>$OUT
#make frameworkinstallmaclib 1>>$OUT 2>>$OUT
#make frameworkinstallunixtools 1>>$OUT 2>>$OUT
#make frameworkaltinstallunixtools 1>>$OUT 2>>$OUT

echo ">> Mounting disk image..."
hdiutil attach $PKG_DIR/python-2.4.4-macosx2006-10-18.dmg 1>>$OUT 2>>$OUT

echo ">> Installing..."
installer -pkg "/Volumes/Univeral MacPython 2.4.4/MacPython.mpkg" -target / 1>>$OUT 2>>$OUT

echo ">> Unmounting disk image..."
hdiutil detach "/Volumes/Univeral MacPython 2.4.4" 1>>$OUT 2>>$OUT

# -----------------------------------------------------------------------------

PYTHON_VERSION=2.4
#PYTHON_ROOT=$SANDBOX_DIR/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
#PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION

PYTHON_ROOT=/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION

# -----------------------------------------------------------------------------

#export CFLAGS="-isysroot /Developer/SDKs/MacOSX10.4u.sdk -arch ppc -arch i386"
#export LDFLAGS="-isysroot /Developer/SDKs/MacOSX10.4u.sdk -arch ppc -arch i386"
#export PYTHONPATH="$PYTHON_ROOT:$PYTHONPATH"

# =============================================================================
# setuptools (latest)
# =============================================================================

#echo "=== SETUPTOOLS ================================================================" >>$OUT
#echo "Setting up setuptools..."
#cd $PKG_DIR
#
#echo ">> Installing..."
#$PYTHON ez_setup.py --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# BerkeleyDB 4.6.21
# =============================================================================

#echo "=== BERKELEY DB 4.6.21 ========================================================" >>$OUT
#echo "Setting up Berkeley DB 4.6.21"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/db-4.6.21.NC.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/db-4.6.21.NC/build_unix
#
#echo ">> Configuring..."
#../dist/configure --prefix=$SANDBOX_DIR 1>>$OUT 2>>$OUT
#
#echo ">> Building..."
#make 1>>$OUT 2>>$OUT
#
#echo ">> Installing..."
#make install 1>>$OUT 2>>$OUT

# =============================================================================
# pybsddb 4.5
# =============================================================================

#echo "=== PYBSDDB 4.5.0 =============================================================" >>$OUT
#echo "Setting up pybsddb 4.5"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/bsddb3-4.5.0.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/bsddb3-4.5.0
#
#echo ">> Building..."
#$PYTHON setup.py --berkeley-db=$SANDBOX_DIR build 1>>$OUT 2>>$OUT
#
#echo ">> Installing..."
#$PYTHON setup.py --berkeley-db=$SANDBOX_DIR install 1>>$OUT 2>>$OUT

# =============================================================================
# SQLite 3.5.2
# =============================================================================

#echo "=== SQLITE 3.5.2 ==============================================================" >>$OUT
#echo "Setting up SQlite 3.5.2"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/sqlite-3.5.2.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/sqlite-3.5.2
#
#echo ">> Configuring..."
#./configure --prefix=$SANDBOX_DIR \
#            --enable-threadsafe \
#            --disable-tcl \
#            --disable-readline \
#             1>>$OUT 2>>$OUT
#
#echo ">> Building..."
#make 1>>$OUT 2>>$OUT
#
#echo ">> Installing..."
#make install 1>>$OUT 2>>$OUT

# =============================================================================
# pysqlite 2.4.0
# =============================================================================

echo "=== PYSQLITE 2.4.0 ============================================================" >>$OUT
echo "Setting up pysqlite 2.4.0"
cd $WORK_DIR

echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/pysqlite-2.4.0.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/pysqlite-2.4.0
unzip $PKG_DIR/pysqlite-2.2.2-py2.4-macosx10.4.zip 1>>$OUT 2>>$OUT

#
#echo ">> Writing custom setup.cfg..."
#cat > setup.cfg <<CONFIG
#[build_ext]
#define=
#include_dirs=$SANDBOX_DIR/include
#library_dirs=$SANDBOX_DIR/lib
#libraries=sqlite3
#CONFIG
#
#echo ">> Building..."
#$PYTHON setup.py build 1>>$OUT 2>>$OUT
#
#echo ">> Installing..."
#$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

echo ">> Installing..."
installer -pkg pysqlite-2.2.2-py2.4-macosx10.4/pysqlite-2.2.2-py2.4-macosx10.4.mpkg -target /Library/Frameworks/Python.framework 1>>$OUT 2>>$OUT

# =============================================================================
# altgraph 0.6.7
# =============================================================================

#echo "=== ALTGRAPH 0.6.7 ============================================================" >>$OUT
#echo "Setting up altgraph 0.6.7"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/altgraph-0.6.7.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/altgraph-0.6.7
#
#echo ">> Building & installing..."
#$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# modulegraph 0.7
# =============================================================================

#echo "=== MODULEGRAPH 0.7 ===========================================================" >>$OUT
#echo "Setting up modulegraph 0.7"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/modulegraph-0.7.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/modulegraph-0.7
#
#echo ">> Building & installing..."
#$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# bdist_mpkg 0.4.3
# =============================================================================

#echo "=== BDIST_MPKG 0.4.3 ==========================================================" >>$OUT
#echo "Setting up bdist_mpkg 0.4.3"
#cd $WORK_DIR
#
#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/bdist_mpkg-0.4.3.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/bdist_mpkg-0.4.3
#
#echo ">> Building & installing..."
#$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# py2app 0.3.6
# =============================================================================

echo "=== PY2APP 0.3.6 ==============================================================" >>$OUT
echo "Setting up py2app 0.3.6"
cd $WORK_DIR

echo ">> Checking out from subversion..."
svn co http://svn.pythonmac.org/py2app/py2app/tags/py2app-0.3.6 py2app-0.3.6 1>>$OUT 2>>$OUT

#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/py2app-0.3.6.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/py2app-0.3.6

echo ">> Building & installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# PyObjC 1.4.1
# =============================================================================

echo "=== PYOBJC 1.4.1 ==============================================================" >>$OUT
echo "Setting up PyObjC 1.4.1"
cd $WORK_DIR

echo ">> Checking out from subversion..."
svn co http://svn.red-bean.com/pyobjc/branches/pyobjc-1.4-branch pyobjc-1.4.1 1>>$OUT 2>>$OUT

#echo ">> Unpacking archive..."
#tar -xzf $PKG_DIR/pyobjc-1.4.tar.gz 1>>$OUT 2>>$OUT
#cd $WORK_DIR/pyobjc-1.4
cd $WORK_DIR/pyobjc-1.4.1

echo ">> Building & installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# macholib 1.2.1
# =============================================================================

$PYTHON_ROOT/bin/easy_install $PKG_DIR/macholib-1.2.1.dev_r23-py2.4.egg

# =============================================================================
# Pyrex 0.9.6.4
# =============================================================================

echo "=== PYREX 0.9.6.4 =============================================================" >>$OUT
echo "Setting up Pyrex 0.9.6.4"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/Pyrex-0.9.6.4.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/Pyrex-0.9.6.4

echo ">> Patching..."
cat > extension.py.patch <<PATCH
18d17
<     _Extension.Extension.__doc__ + \\
PATCH
patch Pyrex/Distutils/extension.py < extension.py.patch 1>>$OUT 2>>$OUT

echo ">> Installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# Psyco 
# =============================================================================

echo "=== Psyco (latest) ============================================================" >>$OUT
echo "Setting up Psyco"

cd $WORK_DIR

echo ">> Fecthing sources from subversion..."
svn co http://codespeak.net/svn/psyco/dist/ psyco 1>>$OUT 2>>$OUT
cd $WORK_DIR/psyco

echo ">> Building..."
$PYTHON setup.py build 1>>$OUT 2>>$OUT

echo ">> Installing..."
$PYTHON setup.py install 1>>$OUT 2>>$OUT

# =============================================================================
# Boost 1.35
# =============================================================================

echo "=== BOOST 1.35 ==============================================================" >>$OUT
echo "Setting up Boost 1.35"
cd $WORK_DIR

tar -xzf $PKG_DIR/boost_1_35_0.tar.gz
cd boost_1_35_0

cd tools/jam/src
./build.sh
cd `find . -type d -maxdepth 1 | grep bin.`
mkdir -p $SANDBOX_DIR/bin
cp bjam $SANDBOX_DIR/bin

cd $WORK_DIR/boost_1_35_0
$SANDBOX_DIR/bin/bjam  --prefix=$SANDBOX_DIR \
                       --with-python \
                       --with-date_time \
                       --with-filesystem \
                       --with-thread \
                       --with-regex \
                       toolset=darwin \
                       architecture=combined \
                       link=static \
                       release \
                       install

# =============================================================================

echo "=== FINISHED ==================================================================" >>$OUT
#echo "Sandbox setup complete, logging signature."
#echo -n $SIGNATURE > $SIGNATURE_FILE

# =============================================================================
