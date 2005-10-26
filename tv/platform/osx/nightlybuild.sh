#!/bin/sh
#
# Automated nightly build script for DTV OS X
# Add this script to your crontab to automatically upload builds to the server
#
# For example, my crontab looks like this:
#
# PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin
# SSH_AUTH_SOCK=/tmp/501/SSHKeychain.socket
# 30 03 * * * /Users/nassar/nightlybuild/dtv/trunk/tv/platform/osx/nightlybuild.sh /Users/nassar/nightlybuild/dtv
#

set -e

# Requires one argument -------------------------------------------------------

if [ $# -lt 1 ] ; then
    echo "usage: $0 buildDir ..." 1>&2
    exit 1
fi

buildDir=$1
imgDirName="img"

# Update from Subversion ------------------------------------------------------

echo "Updating source tree..."
cd "${buildDir}"
svn update

# Build -----------------------------------------------------------------------

echo "Changing to OS X platform directory"
cd trunk/tv/platform/osx

echo -n "Removing old build files... "
rm -rf DTV.app
rm -rf "${imgDirName}"
echo "done."

echo "Building..."
./build.sh

# Prepare the image folder ----------------------------------------------------

echo "Preparing image folder..."

mkdir "${imgDirName}"
mkdir "${imgDirName}/.background"

mv "DTV.app" "${imgDirName}"
cp "Resources-DMG/README IF UPGRADING ON PANTHER.txt" "${imgDirName}/Readme if upgrading on Panther"
cp "Resources-DMG/DS_Store" "${imgDirName}/.DS_Store"
cp "Resources-DMG/background.tiff" "${imgDirName}/.background"

/Developer/Tools/SetFile -a V "${imgDirName}/.DS_Store"
/Developer/Tools/SetFile -c ttxt "${imgDirName}/Readme if upgrading on Panther"
/Developer/Tools/SetFile -t TEXT "${imgDirName}/Readme if upgrading on Panther"

# Create the DMG from the image folder ----------------------------------------

echo "Creating DMG file... "

imgName=DTV-CVS-`date +"%F"`
hdiutil create -srcfolder "${imgDirName}" -volname DTV -format UDZO "DTV.tmp.dmg"
hdiutil convert -format UDZO -imagekey zlib-level=9 -o "${imgName}.dmg" "DTV.tmp.dmg"
rm "DTV.tmp.dmg"

echo "Completed:"
ls -la "${imgName}.dmg"

# Upload DMG to Sourceforge ---------------------------------------------------

echo "Uploading to Sourceforge"

scp "${imgName}.dmg" shell.sf.net:/home/groups/d/de/demotv/htdocs/cvs-snapshots
echo

# And we're all set -----------------------------------------------------------

echo "Done!"
