#!/bin/sh

#
# very simple script to build a broadcast machine zip
#

rm bm.zip
rm -rf bm
svn co https://svn.participatoryculture.org/svn/dtv/trunk/bmachine ./bm
svn co https://svn.participatoryculture.org/svn/dtv/trunk/bmachine-binary-kit ./binaries
cp ./binaries/* ./bm/
find ./bm -name '.svn' -exec rm -rf {} \;
find ./bm -name 'CVS' -exec rm -rf {} \;
zip -r bm.zip bm
