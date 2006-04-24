<?php
/*
	put this in your crontab:
	
	0,10,20,30,40,50 * * * * wget http://URL/cron.php
	
	it'll run every 10 minutes to see if your seeds are running, and if not, it will start them	

 */
include_once "include.php";

$files = $store->getAllFiles();
foreach ($files as $filehash => $file) {

	if (is_local_torrent($file["URL"]) ) {
	
		//
		// make sure this torrent is running (in case the server has crashed, etc
		//
		$torrentfile = local_filename($file["URL"]);
		$torrenthash = $store->getHashFromTorrent($torrentfile);
		$restarted = !$seeder->confirmSeederRunning($torrenthash, $torrentfile);
		
		if ( isset($_GET["debug"]) && $restarted ) {
			print "restarted $torrentfile\n";
		}
	
	}
}
?>