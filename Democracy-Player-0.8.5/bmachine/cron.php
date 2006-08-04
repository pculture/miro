<?php
/*
	put this in your crontab:
	
	0,10,20,30,40,50 * * * * wget http://URL/cron.php
	
	it'll run every 10 minutes to see if your seeds are running, and if not, it will start them	

 */
include_once "include.php";

global $seeder;
$seeder->seedFiles();

?>