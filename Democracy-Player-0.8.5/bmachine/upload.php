<?php
/**
 * take in information about a new torrent, and post it to our data files
 * @package BroadcastMachine
 */

require_once("include.php");

// Return an error if the file can't be found

global $store;

/**
 * note - it seems like we might want to call clearOldAuthHashes here to see if the hash
 * specified here is too old to be valid. (cjm 08/20/2005)
 */


/**
 * Note: There was a bug in an early upload client that sent the hash as
 * "hash" instead of "Hash," so we check for both. Don't expect
 * this to stay here too long
 */
if ( isset($_POST["Hash"]) ) {
  $hash = $_POST["Hash"];
}
else if ( isset($_POST["hash"]) ) {
  $hash = $_POST["hash"];
}

if (
    !isset($_FILES["Torrent"]) ||
    !( isset($hash) && $store->isValidAuthHash($_POST["Username"], $hash) )
    ) {
  
  global $data_dir;
  $handle = fopen($data_dir . '/' . $hash . '.error', "wb+");
  if ( $handle ) {
    fwrite($handle, "This upload is not authorized.");
    fclose($handle);
  }
  
  header("HTTP/1.0 404 Not Found");
  die("Upload failed");
  
 } 
 else {
   
   if (isset($hash)) {
     $store->dropAuthHash($_POST["Username"],$hash,$_FILES['Torrent']['name']);
   }
   
   $torrent = bdecode(file_get_contents($_FILES['Torrent']['tmp_name']));
   
   if (isset($torrent['sha1'])) {

     //debug_message("addTorrentToTracker: try to create $torrent");

     global $torrents_dir;
     $result = move_uploaded_file($_FILES['Torrent']['tmp_name'], $torrents_dir . "/" . $_FILES['Torrent']['name']);
     $store->addTorrentToTracker($_FILES['Torrent']['name']);
   }
   
 }



?>