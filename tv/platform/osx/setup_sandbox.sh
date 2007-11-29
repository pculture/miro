#/bin/bash

# =============================================================================

SANDBOX_VERSION=20071128001

# =============================================================================

if [ -d "../../../dtv-binary-kit-mac" ]; then
    PKG_DIR=$(pushd ../../../dtv-binary-kit-mac/sandbox >/dev/null; pwd; popd  >/dev/null)
else
    root=$(pushd ../../../ >/dev/null; pwd; popd  >/dev/null)
    echo "Could not find the required Mac binary kit which should be at $root/dtv-binary-kit-mac"
    echo "Please check it out first from the Subversion repository."
    exit
fi

# =============================================================================

VERBOSE=no
ROOT_DIR=$(pushd ../../../../ >/dev/null; pwd; popd >/dev/null)

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

SANDBOX_DIR=$ROOT_DIR/sandbox
WORK_DIR=$SANDBOX_DIR/pkg

# =============================================================================

SIGNATURE=$SANDBOX_VERSION
for pkg in $PKG_DIR/*; do
    SIGNATURE="$SIGNATURE $(basename $pkg) $(stat -f '%z' $pkg)"
done
SIGNATURE=$(echo $SIGNATURE | md5)
SIGNATURE_FILE=$SANDBOX_DIR/signature.md5

# =============================================================================

setup_required=no

if [ -d $SANDBOX_DIR ]; then
    echo "Sandbox found, checking signature..."

    if [ -f $SIGNATURE_FILE ]; then
        local_signature=$(cat -s $SIGNATURE_FILE)
        if [ $local_signature == $SIGNATURE ]; then
            echo "Local sandbox is up to date."
        else
            echo "Sandbox signature mismatch, setup required."
            setup_required=yes
        fi
    else
        echo "Unsigned sandbox, setup required."
        setup_required=yes
    fi
    
    if [ $setup_required == yes ]; then
        echo "Deleting current sandbox..."
        rm -rf $SANDBOX_DIR
    fi
else
    echo "Sandbox not found, setup required."
    setup_required=yes
fi

if [ $setup_required == no ]; then
    exit
fi

# =============================================================================

echo "Setting up new sandbox in $ROOT_DIR"
mkdir -p $WORK_DIR

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

echo "=== PYTHON 2.4.4 ==============================================================" >$OUT
echo "Setting up Python 2.4.4"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/Python-2.4.4.tgz 1>>$OUT 2>>$OUT
cd $WORK_DIR/Python-2.4.4

echo ">> Patching configure script..."
sed "s/-arch_only ppc/-arch_only \`arch\`/g" configure > configure.patched
chmod +x configure.patched
mv configure configure.unpatched
mv configure.patched configure

echo ">> Configuring..."
./configure --prefix=$SANDBOX_DIR \
            --enable-framework=$SANDBOX_DIR/Library/Frameworks \
            --enable-shared \
            --with-suffix="" \
            --disable-readline \
            --disable-tk \
            --enable-ipv6 \
             1>>$OUT 2>>$OUT

echo ">> Building & installing..."
make python.exe 1>>$OUT 2>>$OUT
make frameworkinstallstructure 1>>$OUT 2>>$OUT
make bininstall 1>>$OUT 2>>$OUT
make altbininstall 1>>$OUT 2>>$OUT
make libinstall 1>>$OUT 2>>$OUT
make libainstall 1>>$OUT 2>>$OUT
make inclinstall 1>>$OUT 2>>$OUT
make sharedinstall 1>>$OUT 2>>$OUT
make oldsharedinstall 1>>$OUT 2>>$OUT
make frameworkinstallmaclib 1>>$OUT 2>>$OUT
make frameworkinstallunixtools 1>>$OUT 2>>$OUT
make frameworkaltinstallunixtools 1>>$OUT 2>>$OUT

# -----------------------------------------------------------------------------

PYTHON_VERSION=2.4
PYTHON_ROOT=$SANDBOX_DIR/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION

# =============================================================================
# setuptools (latest)
# =============================================================================

echo "=== SETUPTOOLS ================================================================" >$OUT
echo "Setting up setuptools..."
cd $WORK_DIR

echo ">> Installing..."
$PYTHON ez_setup.py --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# BerkeleyDB 4.6.21
# =============================================================================

echo "=== BERKELEY DB 4.6.21 ========================================================" >$OUT
echo "Setting up Berkeley DB 4.6.21"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/db-4.6.21.NC.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/db-4.6.21.NC/build_unix

echo ">> Configuring..."
../dist/configure --prefix=$SANDBOX_DIR 1>>$OUT 2>>$OUT

echo ">> Building..."
make 1>>$OUT 2>>$OUT

echo ">> Installing..."
make install 1>>$OUT 2>>$OUT

# =============================================================================
# pybsddb 4.5
# =============================================================================

echo "=== PYBSDDB 4.5.0 =============================================================" >$OUT
echo "Setting up pybsddb 4.5"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/bsddb3-4.5.0.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/bsddb3-4.5.0

echo ">> Building..."
$PYTHON setup.py --berkeley-db=$SANDBOX_DIR build 1>>$OUT 2>>$OUT

echo ">> Installing..."
$PYTHON setup.py --berkeley-db=$SANDBOX_DIR install 1>>$OUT 2>>$OUT

# =============================================================================
# SQLite 3.5.2
# =============================================================================

echo "=== SQLITE 3.5.2 ==============================================================" >$OUT
echo "Setting up SQlite 3.5.2"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/sqlite-3.5.2.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/sqlite-3.5.2

echo ">> Configuring..."
./configure --prefix=$SANDBOX_DIR \
            --enable-threadsafe \
            --disable-tcl \
            --disable-readline \
             1>>$OUT 2>>$OUT

echo ">> Building..."
make 1>>$OUT 2>>$OUT

echo ">> Installing..."
make install 1>>$OUT 2>>$OUT

# =============================================================================
# pysqlite 2.4.0
# =============================================================================

echo "=== PYSQLITE 2.4.0 ============================================================" >$OUT
echo "Setting up pysqlite 2.4.0"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/pysqlite-2.4.0.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/pysqlite-2.4.0

echo ">> Writing custom setup.cfg..."
cat > setup.cfg <<CONFIG
[build_ext]
define=
include_dirs=$SANDBOX_DIR/include
library_dirs=$SANDBOX_DIR/lib
libraries=sqlite3
CONFIG

echo ">> Building..."
$PYTHON setup.py build 1>>$OUT 2>>$OUT

echo ">> Installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# py2app 0.3.6
# =============================================================================

echo "=== PY2APP 0.3.6 ==============================================================" >$OUT
echo "Setting up py2app 0.3.6"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/py2app-0.3.6.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/py2app-0.3.6

echo ">> Building & installing..."
export PYTHONPATH="$PYTHON_ROOT:$PYTHONPATH"
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# PyObjC 1.4
# =============================================================================

echo "=== PYOBJC 1.4.0 ==============================================================" >$OUT
echo "Setting up PyObjC 1.4"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/pyobjc-1.4.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/pyobjc-1.4

echo ">> Building & installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# Pyrex 0.9.6.2 (0.9.6.3 setup script is currently broken!!)
# =============================================================================

echo "=== PYREX 0.9.6.2 =============================================================" >$OUT
echo "Setting up Pyrex 0.9.6.2"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/Pyrex-0.9.6.2.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/Pyrex-0.9.6.2

echo ">> Installing..."
$PYTHON setup.py install --prefix=$PYTHON_ROOT 1>>$OUT 2>>$OUT

# =============================================================================
# Boost 1.33.1
# (because boost 1.34.x causes the libtorrent python extension to fail)
# =============================================================================

echo "=== BOOST 1.33.1 ==============================================================" >$OUT
echo "Setting up Boost 1.33.1"
cd $WORK_DIR

echo ">> Unpacking archive..."
tar -xzf $PKG_DIR/boost_1_33_1.tar.gz 1>>$OUT 2>>$OUT
cd $WORK_DIR/boost_1_33_1

echo ">> Building the bjam tool..."
cd tools/build/jam_src
./build.sh 1>>$OUT 2>>$OUT

echo ">> Building & installing..."

cd $WORK_DIR/boost_1_33_1
./tools/build/jam_src/bin.macosxppc/bjam --prefix=$SANDBOX_DIR \
                                         --with-python \
                                         --with-date_time \
                                         --with-filesystem \
                                         --with-thread \
                                         --without-icu \
                                         -sCFLAGS="-foo" \
                                         -sPYTHON_ROOT=$PYTHON_ROOT \
                                         -sPYTHON_VERSION=$PYTHON_VERSION \
                                         -sBUILD="release" \
                                         -sTOOLS="darwin" \
                                         install 1>>$OUT 2>>$OUT

echo ">> Removing static libraries..."
rm $SANDBOX_DIR/lib/libboost*.a

echo ">> Updating dynamic libraries identification names.."
for lib in $SANDBOX_DIR/lib/libboost*.dylib
    do
    install_name_tool -id $lib $lib
done

# =============================================================================

echo "=== FINISHED ==================================================================" >>$OUT
echo "Sandbox setup complete, logging signature."
echo -n $SIGNATURE > $SIGNATURE_FILE

# =============================================================================
