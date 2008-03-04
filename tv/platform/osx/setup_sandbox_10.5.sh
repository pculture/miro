#/bin/bash

# =============================================================================

ROOT_DIR=$(pushd ../../../ >/dev/null; pwd; popd >/dev/null)
BKIT_DIR=$ROOT_DIR/dtv-binary-kit-mac/sandbox
SBOX_DIR=$ROOT_DIR/sandbox
WORK_DIR=$SBOX_DIR/pkg

mkdir -p $WORK_DIR

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

python2.5 setup.py --berkeley-db=$SBOX_DIR build
python2.5 setup.py --berkeley-db=$SBOX_DIR install --root=$SBOX_DIR

# Pyrex =======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/Pyrex-0.9.6.4.tar.gz
cd $WORK_DIR/Pyrex-0.9.6.4

python2.5 setup.py build
python2.5 setup.py install --root=$SBOX_DIR

# Boost =======================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/boost_1_34_1.tar.gz
cd $WORK_DIR/boost_1_34_1

cd tools/jam/src
./build.sh
cd `find . -type d -maxdepth 1 | grep bin.`
mkdir $SBOX_DIR/bin
cp bjam $SBOX_DIR/bin

cd $WORK_DIR/boost_1_34_1
$SBOX_DIR/bin/bjam  --prefix=$SBOX_DIR \
                    --with-python \
                    --with-date_time \
                    --with-filesystem \
                    --with-thread \
                    --with-regex \
                    --toolset=darwin \
                    release \
                    install

# libtorrent ==================================================================

cd $WORK_DIR

tar -xzf $BKIT_DIR/libtorrent-0.12.1.tar.gz
cd $WORK_DIR/libtorrent-0.12.1

export CXXFLAGS=-I$SBOX_DIR/include/boost-1_34_1
export LDFLAGS=-L$SBOX_DIR/lib

./configure --prefix=$SBOX_DIR
make
make install

# libtorrent python bindings ==================================================

cd bindings/python

export BOOST_BUILD_PATH=$SBOX_DIR/pkg/boost_1_34_1

$SBOX_DIR/bin/bjam --toolset=darwin \
                   link=static \
                   release

cp bin/darwin/release/dht-support-on/link-static/logging-none/threading-multi/libtorrent.so $SBOX_DIR/Library/Python/2.5/site-packages/libtorrent.so
