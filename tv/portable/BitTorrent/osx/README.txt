>10.2 Jaguar Required!  Sorry...

InternetExplorer users:  You must launch BitTorrent with InternetExplorer NOT RUNNING in order to register as a helper app.  This only needs to be done once.

Safari:  Safari doesn't automatically hand the torrent file off to BitTorrent.  Open the torrent file to start the download.

Mozilla:  Restart Mozilla after launching BitTorrent for the first time.

OmniWeb:  OmniWeb doesn't auto-launch BT.  Just double-click the .torrent file in the download panel or otherwise open the .torrent file to get things started.



Guide to Fast Downloads
-----------------------
The name of the game is connecting to as many peers as possible.  If you are behind a NAT or firewall, the single thing that will make the biggest difference in your download speed is to reconfigure your NAT/firewall to allow incoming connections on the ports that BT is listening to (it uses a new port for every download, starting at the minimum you specify.)  Then all the other peers behind a NAT or firewall will connect to you so that you can download from them.

BitTorrent uses "tit for tat" for deciding which peer to upload to.  In general terms, the client uploads to the peers that it is downloading from the fastest.  This is why there can be a delay after connecting to peers before downloading begins;  you have nothing to upload to other peers.  The torrent typically bursts to life once your client gets a complete piece or two.  If there is excess bandwidth available, perhaps because many peers left their window open, then you can get good download rates without uploading much.  If you are on a very fast connection and think you could be downloading faster, try increasing the maximum number of uploads;  by uploading to more peers you may end up downloading from more peers.  Give the client a few minutes to "settle" after tweaking it.  The client uses one upload "slot" to cycle through peers looking for fast downloads and only changes this slot every 30 seconds.

Release Notes Version 3.3a 2003/11/07
----------
Recompiled with XCode, works on Pathner

Release Notes Version 3.3 2003/10/10
----------
Latest BitTorrent:
  more hard drive friendly file allocation
  less CPU consumption
  many tweaks
Internationalization:
  Better handling of extended characters in filenames.
  Dutch translation contributed by Martijn Dekker
  Partial French translation contributed by ToShyO
Fixed Bugs:
  opened file descriptor limit
  removed illegal characters from Rendezvous advertisements, not compatible with 3.2!

Release Notes Version 3.2.2a 2003/05/31
----------
somehow a typo snuck in unnoticed

Release Notes Version 3.2.2  2003/05/30
----------
Latest BitTorrent
Fixed bug where opening multiple torrent files at once caused a deadlock
New Features:
  Preferences for minimum/maximum port and IP address
  Displays number of peers
  Displays total uploaded / downloaded
  Adjustable max upload rate and max uploads (not surprisingly, this was the most requested feature)
  Rendezvous tracking finds peers on the same side of the firewall and allows "trackerless" operation in the local domain
  Cancel button for torrent generation
    
  
Release Notes Version 3.1a
----------
Fixed a bug where torrents larger than about 2 gigabytes would fail.
These builds do not seem to work on 10.1, the cause is being investigated.  For now you need 10.2 "Jaguar"


Release Notes Version 3.1
----------
This release has the latest BitTorrent and also UI for generating torrent files.
Checking the "create a torrent file for each file/folder in this folder..." will create a torrent file only if one does not already exist.  Also, it only creates torrents for the files/foldes in the top level of the chosen folder.


Release Notes Version 3.0
----------
Initial Mac OS X release
