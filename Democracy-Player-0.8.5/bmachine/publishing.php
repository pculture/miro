<?php
/**
 * library of publishing-related functions
 *
 * pretty much exclusively called from publish.php
 * @package BroadcastMachine
 */


require_once("include.php");
require_once("mime.php");

/**
 * generate a unique filename for the given directory and base file name - we use
 * this to make sure that thumbnails and other uploaded files are always unique, and
 * don't get overwritten.
 */
function unique_file_name( $basedir, $basename ) {

  $ext = ereg_replace("^.+\\.([^.]+)$", "\\1", $basename );
  $hashedname = md5($basename . rand() ) . "." . $ext;

  while ( file_exists($basedir . "/" . $hashedname ) ) {
    $hashedname = md5($basename . rand() ) . "." . $ext;
  }
  
  return $hashedname;
}

/**
 * determine if this file is a valid mimetype
 *
 * we're not really doing anything with this right now
 */
function is_valid_mimetype($type = "text/html") {

  global $do_mime_check;
	
  if ( $do_mime_check != true ) {
    return true;
  }

  if ( beginsWith($type, "video/") ||
       beginsWith($type, "audio/") ||
       $type == "application/x-bittorrent" ) {
    return true;
  }
  
  return false;
}

function max_upload_size() {
  $val = ini_get("upload_max_filesize");
  $val = trim($val);
  $last = strtolower($val{strlen($val)-1});
  switch($last) {
    // The 'G' modifier is available since PHP 5.1.0
  case 'g':
    $val *= 1024;
  case 'm':
    $val *= 1024;
  case 'k':
    $val *= 1024;
  }
  return $val;
}

/**
 * given the $_FILES data for an uploaded file, figure out if it uploaded okay.
 * right now that is just a check to make sure it isn't exactly the 
 * file upload limit for PHP.
 */
function good_upload($file) {
  $max_filesize = max_upload_size();
  $upload_length = filesize( $file['tmp_name'] );

  if ( $upload_length >= $max_filesize || $file['size'] >= $max_filesize || $file['size'] == 0 ) {
    return false;
  }

  return true;	
}

/**
 * ensure that a url is (somewhat) valid
 * submitted by pnomolos -at- gmail.com
 * https://develop.participatoryculture.org/projects/dtv/ticket/846
 */
function check_url($url) {
  if ( "" === $url ) {
    return true;
  }

  // parse it (disable/re-enable warnings in case things are mangled)
  $old_error_level = error_reporting();

  error_reporting ( $old_error_level & ~E_WARNING );

  $url_parts = parse_url($url);
  error_reporting ( $old_error_level );

  // return false if something went seriously 
  // wrong and parse_url couldn't even parse it
  if ( false === $url_parts ) {
    return false;
  }

  $valid_url = true;
  $valid_url = $url_parts['host'] ? 
    preg_match ( '/(?:[0-9]{1,3}\.){3}[0-9]{1,3}/', $url_parts['host'] ) ||
    preg_match ( '/(?:(?:[a-zA-Z0-9]|-)+\\.)+[a-zA-Z]{2,4}/', $url_parts['host'] ) : true;

  // We won't check this for now, just html entity-ify the url
  /* $valid_url = $url_parts['path'] ?
		preg_match ( '#^[^\\{\\}\\|<>\\#\\"]*$#', $url_parts['host'] ) : true;*/

  return $valid_url;
}


function set_file_defaults(&$file) {
  $defaults = array(
		    "ID" => "",
		    "URL" => "",
		    "Title" => "",
		    "Description" => "",
		    "Image" => "http://",
		    "LicenseURL" => "",
		    'LicenseName' => "",
		    "Creator" => "",
		    "Rights" => "",
		    "Keywords" => "",
		    "Webpage" => "",
		    "Mimetype" => "",
		    'RuntimeHours' => "",
		    'RuntimeMinutes' => "",
		    'RuntimeSeconds' => "",
		    "Transcript" => "",
		    'ReleaseDay' => "",
		    'ReleaseMonth' => -1,
		    'ReleaseYear' => "",
		    'Explicit' => 0,
		    'Excerpt' => 0,
		    "SharingEnabled" => false,
		    'ignore_mime' => 0,
		    "People" => array(),
		    'Created' => time(),
		    'Publishdate' => time(),
		    'donation_id' => ""
		    );
  
  foreach($defaults as $key => $value) {
    if ( !isset($file[$key]) ) {
      $file[$key] = $value;
    }
    else if ( is_string($file[$key]) && $key != "ID" && $key != "URL" ) {
      $file[$key] = trim(encode($file[$key]));
    }
  }
  if ( !isset($file["ID"]) ) {
    $file["ID"] = sha1($file["URL"]);
  }
  
  if ( isset($file["Keywords"]) && !is_array($file["Keywords"]) ) {
    $file["Keywords"] = explode("\n", $file["Keywords"]);
  }
  else if ( !isset($file["Keywords"]) ) {
    $file["Keywords"] = array();
  }
  
  if ( isset($file["People"]) && !is_array($file["People"]) ) {
    $file["People"] = explode("\n", $file["People"]);

    //
    // parse people
    //
    $tmp = array();
    $people = array();	

    foreach ($file["People"] as $people_row) {
      if (trim($people_row) != '') {
	$tmp[] = explode(":", encode($people_row));
      }
    }
    
    foreach($tmp as $num => $p) {
      if ( is_array($p) && count($p) == 2) {
	$people[$num] = $p;
      }
    }
  
    $file["People"] = $people;
  }
  else if ( !isset($file["People"]) ) {
    $file["People"] = array();
  }
  
  if ( isset($file["Webpage"]) ) {
    $file["Webpage"] = linkencode($file["Webpage"]);
  }
  else {
    $file["Webpage"] = "";
  }
  
  if ( isset($file["post_publish_month"]) &&
       isset($file["post_publish_day"])&&
       isset($file["post_publish_year"])&&
       isset($file["post_publish_hour"])&&
       isset($file["post_publish_minute"]) ) {
    
    $file["Publishdate"] = strtotime(
				     ($file["post_publish_month"] + 1) . "/" . 
				     $file["post_publish_day"] . "/" . 
				     $file["post_publish_year"] . " " . 
				     $file["post_publish_hour"] . ":" . 
				     $file["post_publish_minute"]);
  }
  else {
    $file["Publishdate"] = time();
  }
  
  if ( !isset($file["post_channels"]) ) {
    $file["post_channels"] = array();
  }
  
}

/**
 * publish a file from POST input
 */
function publish_file(&$file, $check_access = true) {

  global $store;
  global $errorstr;

  //
  // if the user doesn't have upload access, then stop right here
  //
  if ( $check_access == true ) {
    requireUploadAccess();
  }
  set_file_defaults($file);

  if ( beginsWith($file["URL"], "file://") ) {
    $file["URL"] = "";
    $_GET["method"] = "link";
    $errorstr = "NOFILE";
    return false;
  }
  

  // make sure we mark any old channels as needing to be published - this way if
  // a user removes a file from a channel, that feed will be rebuilt
  if ( isset($file["ID"])) {
    foreach ($store->channelsForFile($file["ID"]) as $channelID) {
      $store->setRSSNeedsPublish($channelID);
    }
  }


  if ( isset($file["URL"])) {
    // if the is_external flag was passed along, use that value - this will happen when the user uploads
    // a file which needs a MIME specified - we want to treat that as an uploaded file, not an external URL
    if ( isset($file["is_external"]) ) {
      $is_external = $file["is_external"];
    }
    else {
      $is_external = true;
    }
  }
  else {
    $file["URL"] = "";
    $is_external = false;
  }

  // if the user has changed the URL, let's check for a valid mime again
  if ( isset($file["OldURL"]) && $file["OldURL"] != $file["URL"] ) {
    $file['ignore_mime'] = 0;
  }

  if ( isset($file["Mimetype"]) && $file["Mimetype"] == "application/x-bittorrent" ) {
    $got_mime_type = true;
  }
  else if ( $file['ignore_mime'] == 1 && $file['Mimetype'] != "" ) {
    $got_mime_type = true;
  }
  else {
    $got_mime_type = false;
  }

  
  // if this is a torrent posted with the helper, then we'll have a hash already
  
  //
  // generate the hash which will be used to identify this file
  //
  if (!isset($file["ID"]) || $file["ID"] == "") {
    // add a little random seed to our hash generation - this will typically allow
    // publishing the same URL/file twice, which seems like a good thing, and will
    // also eliminate the incredibly unlikely possibility that two files produce the
    // same hash
    $seed = "";
    for ($i = 1; $i <= 10; $i++) {
      $seed .= substr('0123456789abcdef', rand(0,15), 1);
    }
    $file["ID"] = sha1($file["URL"] . $seed);
  }

  //
  // this is set if the user is uploading a file using http upload
  //
  if (isset($_FILES["post_file_upload"]) && $file["post_use_upload"] == 1 ) {
    
    if ( good_upload($_FILES['post_file_upload']) == false ) {
      global $errorstr;
      $errorstr = "SIZE";
      return false;
    }

    global $torrents_dir;
    make_folder($torrents_dir);
    
    // hold onto the actual name of the file
    global $actual_fname;
    $actual_fname = $_FILES['post_file_upload']['name'];
    
    // use a hashed name so we never overwrite anything
    
    $ext = ereg_replace("^.+\\.([^.]+)$", "\\1", $actual_fname );
    $fname = $file["ID"];
    if ( $ext != "" ) {
      $fname .= "." . $ext;
    }
    
    if (
	move_uploaded_file(
			   $_FILES['post_file_upload']['tmp_name'], 
			   "$torrents_dir/$fname" ) ) {

      chmod("$torrents_dir/$fname", perms_for(FILE_PERM_LEVEL) );
      $file["URL"] = get_base_url() . "$torrents_dir/$fname";
    }
    else {
      global $errorstr;
      $errorstr = "UPLOAD";
      return false;
    }

    
    if ( isset($_FILES["post_file_upload"]["type"]) && 
	 $_FILES["post_file_upload"]["type"] != "" && 
	 is_valid_mimetype($_FILES["post_file_upload"]["type"]) ) {
      $file["Mimetype"] = $_FILES["post_file_upload"]["type"];
      $got_mime_type = true;
      
      if ( $file["Mimetype"] == "application/x-bittorrent" ) {
	global $store;
	
	clearstatcache();
	
	$torrent = bdecode( file_get_contents($torrents_dir . "/" . $fname) );
	
	// we need to generate a hash for sha1
	$user = get_username();
	$store->addAuthHash($user, $torrent["sha1"]);	
	$store->addTorrentToTracker($fname);
      }
    }
    else if ( $file['ignore_mime'] == 0 ) {
      $file["Mimetype"] = @mime_content_type("$torrents_dir/$fname");
      
      if ( $file["Mimetype"] ) {
	$got_mime_type = true;
	
	if ( $file["Mimetype"] == "text/html" ) {
	  $file["Mimetype"] = "application/octet-stream";
	}
      }
    }

  }

  if (!isset($file["Explicit"])) {
    $file["Explicit"] = 0;
  }

  if ( ! isset($file["Excerpt"]) ) {
    $file["Excerpt"] = 0;
  }

  if ( isset($file["Transcript"]) && check_url($file["Transcript"]) ) {
    $file['Transcript'] = htmlentities($file["Transcript"]);
  }
  else {
    $file['Transcript'] = "";
  }
  
  global $text_dir;
  make_folder($text_dir);
  
  if (isset($_FILES["post_transcript_file"]) && $_FILES["post_transcript_file"]["size"] > 0) {
    
    if (move_uploaded_file($_FILES['post_transcript_file']['tmp_name'], 
			   "$text_dir/" . $file["ID"] . ".txt")) {
      chmod("$text_dir/" . $file["ID"], perms_for(FILE_PERM_LEVEL) );
      $file['Transcript'] = get_base_url() . "$text_dir/" . $file["ID"] . ".txt";
    }
  }
  else if (isset($file["post_transcript_text"]) && $file["post_transcript_text"] != "" ) {
    
    $handle = fopen($text_dir . '/' . $file["ID"] . '.txt', "a+b");
    fseek($handle,0);
    flock($handle,LOCK_EX);
    ftruncate($handle,0);
    fseek($handle,0);
    fwrite($handle, $file["post_transcript_text"]);
    fclose($handle);
    
    $file['Transcript'] = get_base_url() . "$text_dir/" . $file["ID"] . ".txt";
  }
  
  //
  // handle any thumbnail that the user posted
  //

  global $thumbs_dir;

  if (isset($_FILES["Image_upload"])) {
    make_folder($thumbs_dir);
    
    $hashedname = unique_file_name($thumbs_dir, $_FILES['Image_upload']['name']);	
    
    if (
	move_uploaded_file(
			   $_FILES['Image_upload']['tmp_name'], 
			   "$thumbs_dir/$hashedname" ) ) {
      
      chmod("$thumbs_dir/" . $hashedname, perms_for(FILE_PERM_LEVEL) );
      $file['Image'] = get_base_url() . "$thumbs_dir/" . $hashedname;
    }
    
  }

  //
  // parse keywords
  //
  $keywords = array();

  if ( isset($file["Keywords"]) ) {
    foreach ($file['Keywords'] as $words) {
      if (trim($words) != '') {
	$keywords[] = encode(trim($words));
      }
    }
  }
  $file['Keywords'] = $keywords;

  /*
  //
  // parse people
  //
  $tmp = array();
  $people = array();	

  if ( isset($file["People"]) ) {
    foreach ($file["People"] as $people_row) {
      print $people_row;
      if (trim($people_row) != '') {
	$tmp[] = explode(":", encode($people_row));
      }
    }

    foreach($tmp as $num => $p) {
      if ( is_array($p) && count($p) == 2) {
	$people[$num] = $p;
      }
    }
  }

  $file["People"] = $people;
  */
	
  if ( !isset($file["Image"]) || $file['Image'] == "http://") {
    $file['Image'] = '';
  }

  $file['Image'] = prependHTTP($file['Image']);

  if ( $file["Mimetype"] == "" && $file['ignore_mime'] == 1 ) {
    $file["Mimetype"] = get_mime_from_extension($file["URL"]);
    $got_mime_type = true;
  }

  //
  // if we've got a URL here, let's try and figure out the content-type
  //
  if ( $got_mime_type == false ) {
    
    if ( isset($_POST["mime_chooser"]) ) {
      $file["Mimetype"] = $_POST["mime_chooser"];
      $file['ignore_mime'] = 1;
    }
    else if ( isset($_POST["mime_chooser_custom"]) && $_POST["mime_chooser_custom"] != "" ) {
      $file["Mimetype"] = $_POST["mime_chooser_custom"];
      $file['ignore_mime'] = 1;		
    }
    else {
      $errstr = "";
      
      // encode the link in case it has spaces or other weird characters in it
      $file["Mimetype"] = get_content_type(linkencode($file["URL"]), $errstr);
      
      // we got an error, set our global error variable and exit out
      if ( $errstr ) {
	global $errorstr;
	$errorstr = $errstr;
	return false;
      }
    }
  }

  // check to see if this is a valid mime - if not we'll report the problem to the user
  // and give them a chance to ignore it or choose a different file
  if ( ! is_valid_mimetype($file["Mimetype"]) && 	
       ! ( isset($file['ignore_mime']) && $file['ignore_mime'] == 1 ) ) {
    
    global $errorstr;
    $errorstr = "MIME";
    
    // if this was an uploaded file, we need to specify it's current URL, so we don't have to force the
    // user to start over
    if (isset($_FILES["post_file_upload"]) && $_FILES["post_file_upload"]["size"] > 0 ) {
      global $uploaded_file_url;
      $uploaded_file_url = get_base_url() . "torrents/" . $fname;
    }
    
    return false;
    
  }

  //
  // we'll share this file if the checkbox was checked, and it happens to be
  // a local torrent file
  //
  $sharing_enabled = isset($file["sharing_enabled"]) &&
    (
     (isset($file["ID"]) && $file["ID"] != "") ||
     (isset($file["URL"]) && is_local_torrent($file["URL"]))
     );
  
  //
  // figure out which RSS feeds need to be rebuilt
  //
  $store->setRSSNeedsPublish("ALL");
  
  if ( isset($file["post_channels"]) && count($file["post_channels"]) > 0 ) {
    foreach ($file["post_channels"] as $channelID) {
      $store->setRSSNeedsPublish($channelID);
    }
  }


  //
  // lets figure out if we have a local file or a remote URL here.
  // if it's a file, then we will also check and see if it's a torrent
  //	
  global $data_dir;
  global $torrents_dir;
  if ( file_exists("$data_dir/" . $file["URL"] ) ) {
    
    // data/$file["URL"] will contain the name of the torrent
    $handle = fopen($data_dir . '/' . $file["URL"], "r+");
    if ( $handle ) {
      $torrent = fread($handle, 1024);
      fclose($handle);
      $file["URL"] = get_base_url() . $torrents_dir . '/' . $torrent;
    }
  }


  //
  // create a new file entry, load in our data, and save it
  //
  $newcontent = $store->getFile($file["ID"]);

  // grab our old donation_id - if it was set, then we'll unset it if needed
  if ( isset($newcontent) && isset($newcontent['donation_id']) ) {
    $old_donation_id = $newcontent['donation_id'];
  }
  else {
    $old_donation_id = "";
  }
  
  foreach($file as $key => $value) {
    $newcontent[$key] = $value;
  }
  
  // keep track of if this is a posted URL, or a torrent/uploaded file.  posted URLs
  // will have slightly different logic - we won't check to see if they are files
  // under the control of Broadcast Machine
  if ( ! isset($newcontent) && isset($is_external) ) {	
    $newcontent["External"] = $is_external ? 1 : 0;
  }
  
  //
  // use the actual filename if we have it - we'll use this in download.php for prettier filenames
  //
  global $actual_fname;
  if ( (!isset($actual_fname) || $actual_fname == "") && 
       isset($file["actual_fname"])
       ) {
    $actual_fname = $file["actual_fname"];
  }
  
  if ( isset($actual_fname) && $actual_fname != "" ) {
    $newcontent['FileName'] = encode($actual_fname);	
  }
  else if ( isset($file['actual_fname']) && $file['actual_fname'] != "" ) {
    $newcontent['FileName'] = encode($file['actual_fname']);
  }

  // we'll only do this mime check the first time we try and save a file,
  // so force it to be set after that
  $newcontent['ignore_mime'] = 1;
	
  $newcontent['SharingEnabled'] = $sharing_enabled;

  if (!isset($newcontent['Publisher'])) {
    if (isset($_SESSION['user']['Name'])) {
      $newcontent['Publisher'] = $_SESSION['user']['Name'];
    }
  }

  // let's unset some elements we don't need
  $tmpvals = array(
		   "post_create_day",
		   "post_create_month",
		   "post_create_year",
		   "post_create_hour",
		   "post_create_minute",
		   "post_publish_day",
		   "post_publish_month",
		   "post_publish_year",
		   "post_publish_hour",
		   "post_publish_minute",
		   "x",
		   "y",
		   "_x",
		   "_y",
		   "post_transcript_text",
		   "post_do_save",
		   "post_file_upload",
		   "post_use_upload",
		   "post_license_name",
		   "People_name",
		   "People_role",
		   "videos",
		   "actual_fname",
		   "mime_chooser",
		   "mime_chooser_custom",
		   "method",
		   "OldURL"
		   );

  foreach($tmpvals as $tmp) {
    unset($newcontent[$tmp]);	
  }

  $store->store_file($newcontent, $file["ID"]);

  //
  // add to the donation setup, if it exists
  //
  if ( $old_donation_id != $file["donation_id"] ) {
    if ( $old_donation_id != "" ) {
      $store->removeFileFromDonation($file["ID"], $old_donation_id);
    }
    
    if ( $file['donation_id'] != "" ) {
      $store->addFileToDonation($file["ID"], $file['donation_id']);
    }
  }
  
  //
  // write out any channel info
  //
  $channels = $store->getAllChannels();

  if ( isset($channels) && is_array($channels) ) {
    foreach ($channels as $channel) {
      if (is_admin() || ( isset($channel["OpenPublish"]) && $channel["OpenPublish"]) ) {
	$keys = $channel['Files'];
      
	//
	// first, unset any channels that this was published to
	//
	foreach ($keys as $key_id => $key) {
	  if ($key[0] == $file["ID"]) {
	    $store->removeFileFromChannel($channel, $file["ID"], $key_id);
	    unset($channel['Files'][$key_id]);
	  }
	}
      
      
	if ( isset($file["post_channels"]) && count($file["post_channels"]) > 0 &&
	     in_array($channel['ID'], $file["post_channels"]) ) {
	
	  $sections = array_keys($channel['Sections']);
	
	  foreach ($sections as $section) {
	    $keys = array_keys($channel['Sections'][$section]['Files']);
	  
	    foreach ($keys as $key) {
	      $file = $channel['Sections'][$section]['Files'][$key];
	      if ($file == $file["ID"]) {
		$store->removeFileFromChannelSection($channel, $section, $key);
		unset($channel['Sections'][$section]['Files'][$key]);
	      }
	    }
	  }
	}
	
	$channels[$channel['ID']] = $channel;
      
      }
    } // foreach
  } // if

  if ( isset($file["post_channels"]) && count($file["post_channels"]) > 0 ) {
    foreach ($file["post_channels"] as $channelID) {
      
      error_log("check channels for $channelID");
      if ($channelID != '') {
	
	//
	// add the file to the channel
	//
	if ( is_admin() || (isset($channels[$channelID]["OpenPublish"]) && $channels[$channelID]["OpenPublish"])) {

	  error_log("publish file to " . $channel["ID"]);

	  if ( !isset($file['Publishdate']) || $file['Publishdate'] <= 1 ) {
	    $file['Publishdate'] = time();
	  }
	  $channels[$channelID]["Files"][] = array($file["ID"], $file['Publishdate']);
	  $store->saveChannel($channels[$channelID]);
	}
	
      }
    }
  }
	
  // generate any needed RSS files
  $store->generateRSS();

  global $seeder;
  global $settings;

  //
  // if this is a torrent, and we're configured to share all torrents, then
  // start sharing it
  //
  if ( 
      // is a local torrent
      is_local_torrent($file["URL"]) && 
      
      // sharing is turned on
      isset($settings['sharing_enable']) && $settings['sharing_enable'] == 1 &&
      
      (
       // it's shared - OR - 
       $sharing_enabled == true ||
       
       // global sharing is on		
       (isset($settings['sharing_auto']) && $settings['sharing_auto'] == 1)
       )
      ) {
    $torrentfile = local_filename($file["URL"]);
    $seeder->spawn($torrentfile);
  }
  
  return true;
}
?>