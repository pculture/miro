#!/bin/sh
#
# Automated nightly build script for DTV OS X
#
# Based on script posted to the projectbuilder-users list by Mike Ferris then
# modified for vlc by Jon Lech Johansen
#
# Add this script to your crontab to automatically upload builds to the server
#
# For example, my crontab looks like this:
#
# PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin
# SSH_AUTH_SOCK=/tmp/501/SSHKeychain.socket
# 30 03 * * * /Users/nassar/nightlybuild/dtv/trunk/tv/platform/osx/nightlybuild.sh /Users/nassar/nightlybuild/dtv
#
#

set -e

# Requires one argument
if [ $# -lt 1 ] ; then
    echo "usage: $0 buildDir ..." 1>&2
    exit 1
fi

buildDir=$1

echo "Updating the source tree..."
cd "${buildDir}"
svn update

echo "Changing to OS X platform directory"
cd trunk/tv/platform/osx

echo -n "Removing old DTV.app..."
rm -rf DTV.app img
echo "done."

./build.sh
mkdir img
mv "DTV.app" img
cp "notes/README IF UPGRADING ON PANTHER.txt" img

# Grab size and name
imgName=DTV-CVS-`date +"%F"`
dirName=img

imgSize=`du -sk ${dirName} | cut -f1`
imgSize=$((${imgSize} / 1024 + 2))

if [ $((${imgSize} < 5)) != 0 ] ; then
    imgSize=5;
fi

# Create the image and format it
rm -f "${imgName}.dmg"
echo; echo "Creating ${imgSize} MB disk image named ${imgName}"
hdiutil create "${imgName}.dmg" -megabytes "${imgSize}" -layout NONE -quiet
dev=`hdid -nomount "${imgName}.dmg" | grep '/dev/disk[0-9]*' | cut -d " " -f 1`
/sbin/newfs_hfs -w -v "${imgName}" -b 4096 "${dev}" > /dev/null

# Mount the image and copy stuff
mkdir ./mountpoint
mount -t hfs ${dev} ./mountpoint

echo "Copying contents to ${imgName}:"
for i in ${dirName}/* ; do
    echo "  ${i}"
    /Developer/Tools/CpMac -r "${i}" ./mountpoint
done

umount ./mountpoint
rmdir ./mountpoint
hdiutil eject "${dev}" -quiet

# Compress the image
echo "Compressing ${imgName} disk image"
mv "${imgName}.dmg" "${imgName}.orig.dmg"
hdiutil convert "${imgName}.orig.dmg" -format UDZO -o "${imgName}" -quiet
rm "${imgName}.orig.dmg"

# Done
echo; echo "Disk image creation completed:"
ls -la "${imgName}.dmg"; echo

echo "Uploading to server"
scp "${imgName}.dmg" shell.sf.net:/home/groups/d/de/demotv/htdocs/cvs-snapshots
echo
echo "Done!"
