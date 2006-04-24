<?php
/**
 * file detail display
 * @package Broadcast Machine
 */
require_once("include.php");

// processing here in case our rewrite rules choke
if ( !isset($_GET["i"]) && !isset($_GET["c"]) ) {
	$params = split("/", $_SERVER['REQUEST_URI']);

	if ( count($params) == 5 ) {
		$_GET["c"] = $params[3];
		$_GET["i"] = $params[4];
	}
}


if(!isset($_GET["i"]) || !isset($_GET["c"])) {
  header('Location: ' . get_base_url() . "index.php" );
  exit;
}

$file = $store->getFile($_GET["i"]);
$channel = $store->getChannel($_GET["c"]);

if ( !isset($file) ) {
	die("Couldn't find your file");
}

$channel = $store->getChannel($_GET["c"]);
if ( !isset($channel) ) {
	die("Couldn't find channel");
}

if ( ! $store->channelContainsFile($_GET["i"], $channel) ) {
	die("Wrong channel for this file!");
}

render_detail_page($file, $channel);


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>