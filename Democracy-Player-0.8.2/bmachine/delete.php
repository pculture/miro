<?php
/**
 * handles deleting channels and files
 * @package Broadcast Machine
 */

require_once("include.php");

// don't allow non-admin to delete (bug #1229195 )
if ( ! is_admin() ) {
	header("Location: " . get_base_url() . "index.php");
	exit;
}

//
// - i is the key of the file we want to delete
//
if (isset($_GET['i']) && isset($_GET['t']) ) {
	$id = $_GET['i'];
	$type = $_GET['t'];

	//
	// delete a video
	//
	if ($type == "v") {

		if ( ! ( is_admin() || $owner == get_username() ) ) {
			global $errstr;
			$errstr = "You don't have the permissions to delete this file!";
			$result = false;
		}
		else {
			$result = $store->DeleteFile($id);
		}

		if ( $result == false ) {
			global $errstr;
			if ( isset($errstr) && $errstr != "" ) {
				die($errstr);
			}
			else {
				die("There was an error while deleting the file");
			}
		} // if ( result false )

		$done = get_base_url() . "edit_videos.php";

	}  // if ( type == video )
	
	//
	// delete an entire channel
	//
	else if ($type == 'c') {

		if ( ! is_admin() ) {
			global $errstr;
			$errstr = "You don't have the permissions to delete this channel!";
			$result = false;
		}
		else {
			$result = $store->DeleteChannel($id);
		}

		if ( $result == false ) {
			global $errstr;
			if ( isset($errstr) && $errstr != "" ) {
				die($errstr);
			}
			else {
				die("There was an error while deleting the channel");
			}
		} // if ( result false )
		

		$done = get_base_url() . "channels.php";
	}
}

header('Location: ' . $done . "" );

?>
