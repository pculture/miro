#!/bin/sh

h2def=`pkg-config --variable=codegendir pygobject-2.0`/h2def.py

BUILD_INFO='build-info-defs'

echo "fixed-list-store.defs was built with h2def.py from " > ${BUILD_INFO}
echo "pygobject version" `pkg-config --modversion pygobject-2.0` >> ${BUILD_INFO}

python ${h2def} fixed-list-store.h > fixed-list-store.defs

