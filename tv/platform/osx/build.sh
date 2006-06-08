#!/bin/sh
imgDirName="img"
imgName=Democracy-`date +"%F"`

/usr/bin/env python2.4 setup.py py2app --dist-dir .

if [ "$1" == '-make-dmg' ] ; then
echo "Building image..."
echo "Preparing image folder..."

rm -rf "${imgDirName}"
rm -f "${imgName}.dmg"

mkdir "${imgDirName}"
mkdir "${imgDirName}/.background"

mv "Democracy.app" "${imgDirName}"
cp "Resources-DMG/DS_Store" "${imgDirName}/.DS_Store"
cp "Resources-DMG/background.tiff" "${imgDirName}/.background"

/Developer/Tools/SetFile -a V "${imgDirName}/.DS_Store"

# Create the DMG from the image folder ----------------------------------------

echo "Creating DMG file... "

hdiutil create -srcfolder "${imgDirName}" -volname Democracy -format UDZO "Democracy.tmp.dmg"
hdiutil convert -format UDZO -imagekey zlib-level=9 -o "${imgName}.dmg" "Democracy.tmp.dmg"
rm "Democracy.tmp.dmg"

echo "Completed"
ls -la "${imgName}.dmg"

fi

echo Done.
