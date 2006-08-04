<?php
/**
 * file detail display
 * @package BroadcastMachine
 */
require_once("include.php");

// processing here in case our rewrite rules choke
if ( !isset($_GET["i"]) && !isset($_GET["c"]) ) {
	$params = split("/", $_SERVER['REQUEST_URI']);

  $_GET["c"] = $params[ count($params) - 2 ];
  $_GET["i"] = $params[ count($params) - 1 ];
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
	die("No such file in this channel");
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