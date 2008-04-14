#/bin/bash

# =============================================================================

ROOT_DIR=$(pushd ../../../ >/dev/null; pwd; popd >/dev/null)
BKIT_DIR=$ROOT_DIR/dtv-binary-kit-mac/sandbox
SBOX_DIR=$ROOT_DIR/sandbox
WORK_DIR=$SBOX_DIR/pkg

TARGET_OS_VERSION=10.5
SDK_DIR="/Developer/SDKs/MacOSX$TARGET_OS_VERSION.sdk"

mkdir -p $WORK_DIR

# Python ======================================================================

PYTHON_VERSION=2.5
PYTHON_RELEASE_VERSION=2.5

cd $WORK_DIR
tar -xzf $BKIT_DIR/Python-$PYTHON_RELEASE_VERSION.tgz
cd Python-$PYTHON_RELEASE_VERSION

patch -p0 < $BKIT_DIR/patches/Python/Makefile.pre.in.patch

./configure --prefix=$SBOX_DIR \
            --enable-universalsdk=$SDK_DIR \
            --enable-framework=$SBOX_DIR/Library/Frameworks \
            --with-suffix="" \
            --enable-ipv6

echo '#define SETPGRP_HAVE_ARG' >> pyconfig.h

make
make install

PYTHON=$SBOX_DIR/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION/bin/python

# =============================================================================

export CFLAGS="-mmacosx-version-min=$TARGET_OS_VERSION -isysroot $SDK_DIR -arch ppc -arch i386"
export LDFLAGS=$CFLAGS

# PyObjC ======================================================================

cd $WORK_DIR
svn co http://svn.red-bean.com/pyobjc/trunk/pyobjc PyObjC-2.0
cd PyObjC-2.0

for proj in altgraph \
            macholib \
            modulegraph \
            py2app \
            pyobjc-core \
            pyobjc-metadata \
            pyobjc-framework-Cocoa \
            pyobjc-framework-QTKit \
            pyobjc-framework-Quartz \
            pyobjc-framework-WebKit \
            pyobjc-framework-ExceptionHandling
do
    pushd $proj
    $PYTHON setup.py install
    popd
done

# BerkeleyDB ==================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/db-4.6.21.NC.tar.gz
cd $WORK_DIR/db-4.6.21.NC/build_unix

../dist/configure --prefix=$SBOX_DIR
make
make install

# pybsddb =====================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/bsddb3-4.5.0.tar.gz
cd $WORK_DIR/bsddb3-4.5.0

$PYTHON setup.py --berkeley-db=$SBOX_DIR build
$PYTHON setup.py --berkeley-db=$SBOX_DIR install

# Pyrex =======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/Pyrex-0.9.6.4.tar.gz
cd $WORK_DIR/Pyrex-0.9.6.4

$PYTHON setup.py build
$PYTHON setup.py install

# Psyco =======================================================================

cd $WORK_DIR
svn co http://codespeak.net/svn/psyco/dist/ psyco
cd $WORK_DIR/psyco

$PYTHON setup.py build
$PYTHON setup.py install

# Boost =======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/boost_1_35_0.tar.gz
cd boost_1_35_0

cd tools/jam/src
./build.sh
cd `find . -type d -maxdepth 1 | grep bin.`
mkdir -p $SBOX_DIR/bin
cp bjam $SBOX_DIR/bin

cd $WORK_DIR/boost_1_35_0
$SBOX_DIR/bin/bjam  --prefix=$SBOX_DIR \
                    --with-python \
                    --with-date_time \
                    --with-filesystem \
                    --with-thread \
                    --with-regex \
                    toolset=darwin \
                    macosx-version=$TARGET_OS_VERSION \
                    architecture=combined \
                    link=static \
                    release \
                    install
