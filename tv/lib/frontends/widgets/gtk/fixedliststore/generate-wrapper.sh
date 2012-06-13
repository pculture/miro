#!/bin/sh

BUILD_INFO='build-info-wrapper'

echo "fixed-list-store.defs was built with pyobject-codegen-2.0 " > ${BUILD_INFO}
echo "from pygobject version" `pkg-config --modversion pygobject-2.0` >> ${BUILD_INFO}

DEFS=`pkg-config --variable=defsdir pygtk-2.0`

pygobject-codegen-2.0 --prefix miro_fixed_list_store \
        --register ${DEFS}/gdk-types.defs \
        --register ${DEFS}/gtk-types.defs \
        --override fixed-list-store.override \
        fixed-list-store.defs > fixed-list-store-wrapper.c
