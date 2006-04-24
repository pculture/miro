<?php 
        
/** datastore.php
 * classes for handling storing/accessing data
 * This file is part of BlogTorrent http://www.blogtorrent.com/
 * nassar 'at' downhillbattle 'dot' org
 * Licensed under the terms of the GNU GPL 
 * 
 * Stores data in a flat file database
 * Tracker info is stored in binary format using 7 bytes per client
 * in the following format:
 * [Seeder: 1 bit][Time: 7bits][IP: 4 bytes][Port: 2 bytes]
 * 
 * User info is stored in a bencoded file
 * @package Broadcast Machine
 */

include_once "zipfile.php";
include_once "data_layer.php";
include_once "mysql_layer.php";

global $data_dir;
global $thumbs_dir;
global $torrents_dir;
global $publish_dir;
global $rss_dir;
global $text_dir;

class DataStore {

  var $error;
	var $layer;
	var $is_setup;

	/**
	 * constructor
	 * force_flat - if true, don't even try and use the MySQL layer - we can use this
	 * to have two layers and transfer data between them.
	 */
	function DataStore($force_flat = false) {

    debug_message("DataStore constructor");

		if ( $force_flat == false ) {
      debug_message("Trying MySQL");
			$this->layer = new MySQLDataLayer();
	
			if (!$this->layer->setup()) {
        debug_message("couldn't attach to mysql");
				$this->layer = new BEncodedDataLayer();
				if (!$this->layer->setup()) {
					$this->is_setup = false;
				}
			}
      else {
        $this->is_setup = true;
      }
		}


    if ( $this->is_setup == false ) {
      debug_message("forced to use flat file");
			$this->layer = new BEncodedDataLayer();
			if (!$this->layer->setup()) {
				$this->is_setup = false;
			}
      else {
        $this->is_setup = true;
      }
    }


		
    debug_message("Register hooks");

		//
		// register some hooks which will be called at different places
		// when we load/save/delete data
		//
		
		$this->layer->registerHook("files", "pre-delete", "PreDeleteFile");
		$this->layer->registerHook("files", "post-delete", "PostDeleteFile");

		if ( $this->layer->type() == "flat file" ) {
			$this->layer->registerHook("files", "get", "FileHook");
			$this->layer->registerHook("channels", "get", "FlatGetChannelHook");
		}
		else {
			$this->layer->registerHook("files", "get", "MySQLFileHook");
			$this->layer->registerHook("files", "pre-save", "MySQLPreSaveFileHook");
			$this->layer->registerHook("files", "save", "MySQLSaveFileHook");
			$this->layer->registerHook("channels", "pre-save", "MySQLPreSaveChannelHook");
			$this->layer->registerHook("channels", "save", "MySQLSaveChannelHook");
			$this->layer->registerHook("channels", "get", "MySQLGetChannelHook");
			$this->layer->registerHook("channels", "pre-delete", "MySQLDeleteChannelHook");
			$this->layer->registerHook("donations", "get", "MySQLGetDonationHook");
		}
	}
	
	/**
	 * initialization
	 */
	function init() {
		$this->layer->init();
	}

  /**
   * return the type of file store object
   * @returns type of object as a string
   */
  function type() {
    return $this->layer->type();
  }

	/**
	 * save the settings info for this installation
	 */
	function saveSettings($s) {
		return $this->layer->saveSettings($s);
	}

	/**
	 * load the settings info for this installation
	 */
	function loadSettings() {
		return $this->layer->loadSettings();
	}

  /**
   * get all of our files
   * @returns array of files
   */
  function getAllFiles() {
		debug_message("getAllFiles");
		return $this->layer->getAll("files");
  }

  /**
   * given a hash, return its file
   * @returns file array
   */
  function getFile( $hash, $handle = null ) {
		$f = $this->layer->getOne("files", $hash, $handle);
    if ( count($f) > 0 ) {
      return $f;
    }
    return null;
  }

  /**
   * given a channel ID, figure out when RSS was last generated
   * @returns file array
   */
  function getRSSPublishTime( $channel = "ALL" ) {
    debug_message("getRSSPublishTme $channel");
		$f = $this->layer->getOne("rss", $channel);
    if ( count($f) > 0 && isset($f["lastdate"]) ) {
      return $f["lastdate"];
    }
    return 0;
  }

	/**
	 * store the data for a single file
	 */
  function setRSSPublishTime( $channel = "ALL", $time = -1 ) {
    debug_message("setRSSPublishTme $channel $time");
		if ( $time <= -1 ) {
			$time = time();
		}
		$content["lastdate"] = $time;
		$content["channel"] = $channel;
		$this->layer->saveOne("rss", $content, $channel);
  }

	/**
	 * store the data for a single file
	 */
  function setRSSNeedsPublish( $channel = "ALL" ) {
    debug_message("setRSSNeedsPublish $channel");
		$f = $this->layer->getOne( "rss", $channel );
		$f["time"] = time();
		$f["channel"] = $channel;
    debug_message("setRSSNeedsPublish - save data");
		$this->layer->saveOne("rss", $f, $channel);
  }
	

	function generateRSS() {
    debug_message("generateRSS");
		$rss = $this->layer->getAll("rss");
		
		$make_all = false;

		foreach($rss as $r) {
			if ( !isset($r["lastdate"]) || $r["lastdate"] <= $r["time"] ) {
				$make_all = true;

        debug_message("generateRSS: " . $r["channel"] );

				makeChannelRss($r["channel"], false);
				$r["lastdate"] = time();
				$this->layer->saveOne("rss", $r, $r["channel"]);
			}
		}
		
		if ( $make_all == true ) {
			makeChannelRss("ALL", false);
		}
	}
	
  /**
   * given a filename, try and figure out what its hash is
   */
	function getHashFromFilename($fname) {
	
		// todo - we can have a much faster mysql version
	
		$files = $this->getAllFiles();
		foreach ( $files as $hash => $f ) {
			if ( $f["FileName"] == $fname ) {
				return $hash;
			}
		}
		
		return null;
	}

	/**
	 * delete the specified file
	 * @returns true if successful, false on error and sets global $errstr
	 */
	function DeleteFile($id) {
		return $this->layer->deleteOne("files", $id);
	} // DeleteFile
	

	/**
	 * delete the specified channel
	 * @returns true if successful, false on error and sets global $errstr
	 */
	function DeleteChannel($id) {
		return $this->layer->deleteOne("channels", $id);
	}
	
  /**
   * get an array of all of our channels
   * @returns array of channels
   */
  function getAllChannels() {
		return $this->layer->getAll("channels");
  }

	/**
	 * return the data for the specified channel
	 */	
	function getChannel($id) {
		return $this->layer->getOne("channels", $id);
	}

	/**
	 * determine if the given file is actually published to the given channel.  this prevents
	 * hackers from doing simple tricks like changing the channel ID to get to a file which shouldn't
	 * be publicly available
	 */
	function channelContainsFile($filehash, &$channel) {
		$channel_files = $channel["Files"];
	 	foreach($channel_files as $cf) {
			if ( $cf[0] == $filehash ) {
				return true;
			}
		}
		
		return false;
	}

	/**
	 * return an array of channel IDs that contain this file
	 */
	function channelsForFile($filehash) {

		$out = array();
		$channels = $this->getAllChannels();
		foreach($channels as $c ) {
			if ( $this->channelContainsFile($filehash, $c) ) {
				$out[] = $c["ID"];			
			}
		}	
		return $out;
	}

	/**
	 * remove the file from the specified channel
	 */
	function removeFileFromChannel($channel, $key, $index = -1) {

		$this->layer->lockResources( array("channels", "channel_files") );

		if ( $this->layer->type() == "flat file" ) {

			if ( $index != -1 ) {
				unset($channel['Files'][$index]);
			}
			else {
				$keys = $channel['Files'];
	
				//
				// first, unset any channels that this was published to
				//
				foreach ($keys as $key_id => $key) {
					if ($key[0] == $filehash) {
						unset($channel['Files'][$key_id]);
					}
				}
			}

			$this->saveChannel($channel);	
		}
		else {
      //			$this->layer->removeFileFromChannel($channel, $key);
      $qarr = $this->layer->getTableQueries("channel_files");
      $sql = $qarr["delete_by_file"];
      $sql = str_replace("%key", $key, $sql);
      $sql .= " AND channel_id = " . $channel["ID"];
      $result = do_query( $sql );
		}

		$this->layer->unlockResources( array("channels", "channel_files") );
	}

	/**
	 * remove the file from the specified channel_section
	 */
	function removeFileFromChannelSection($channel, $section, $key) {
		$this->layer->lockResources( array("channels", "channel_sections") );
		if ( $this->layer->type() == "flat file" ) {
			unset($channel['Sections'][$section]['Files'][$key]);
			$this->saveChannel($channel);	
		}
		else {
			$this->layer->removeFileFromChannelSection($channel, $key);
		}
		$this->layer->unlockResources(array("channels", "channel_sections") );
	}


  /**
   * get an array of all of our donation links
   * @returns array of donation links
   */
  function getAllDonations() {
		return $this->layer->getAll("donations");
  }

  /**
   * get the given donation by id
   * @returns array of donation data
   */
  function getDonation($id) {
		return $this->layer->getOne("donations", $id);
  }

  /**
   * remove the specified file from the given donation setup
   */
	function removeFileFromDonation($id, $donation_id) {
		$this->layer->lockResources( array("donations", "donation_files") );
		if ( $this->layer->type() == "flat file" ) {
			$donations = $this->layer->getAllLock("donations", $handle);
			if ( isset($donations[$donation_id]) && isset($donations[$donation_id]['Files'][$id]) ) {
				unset($donations[$donation_id]['Files'][$id]);
			}
			$this->layer->saveAll("donations", $donations, $handle);
		}
		else {
      $qarr = $this->layer->getTableQueries("donation_files");
      $sql = $qarr["delete"];
      $sql = str_replace("%key", $donation_id, $sql);
      $sql = str_replace("%hash", $id, $sql);
      $result = do_query( $sql );
		}

		$this->layer->unlockResources( array("donations", "donation_files") );
	}
	
  /**
   * add the specified file to the given donation setup
   */
	function addFileToDonation($id, $donation_id) {
		$this->layer->lockResources( array("donations", "donation_files") );
		if ( $this->layer->type() == "flat file" ) {
      $donations = $this->layer->getAllLock("donations", $handle);
	
      if ( $donation_id != "" && isset($donations[$donation_id]) ) {
        $donations[$donation_id]['Files'][$id] = 1;	
        $this->layer->saveAll("donations", $donations, $handle);
      }

    }
    else {
      $tmp = array();
      $tmp["id"] = $donation_id;
      $tmp["hash"] = $id;
			$data = $this->layer->prepareForMySQL($tmp);

      $qarr = $this->layer->getTableQueries("donation_files");
      $sql = $qarr["insert"];
			$sql = str_replace("%vals", $data, $sql);
      do_query( $sql );
    }
		$this->layer->unlockResources( array("donations", "donation_files") );
  }
    

  /**
   * get an array of user data
   * @returns user data
   */
  function getAllUsers() {

    $this->layer->lockResources("users");

    debug_message("get users");
		$usertmp = $this->layer->getAll("users");
		$users = array();

		$idx = 1;
		if ( isset($usertmp) && is_array($usertmp) ) {
			foreach ($usertmp as $person) {
	
				if ( !isset($person['Name']) || $person['Name'] == "" ) {
					$person['Name'] = "unknown" . $idx;
					$idx++;
				}


        if ( !isset($person['Username']) ) {
        }
        else {
					$users[$person['Username']] = $person;
        }
			}
		}	
				
		//
		// if we had some screwy user data, then let's rewrite the file so it doesn't happen again
		//
		if ( $idx > 1 ) {
      debug_message("save users to fix data");
      $this->layer->saveAll("users", $users);
     }

    $this->layer->unlockResources("users");
		return $users;
  }

  /**
   * get a user
   * @returns array of userdata
   */
  function getUser($username) {
		$tmp = $this->layer->getOne("users", $username);
    if ( count($tmp) > 0 ) {
      return $tmp;
    }
    return null;
  }

  /**
   * Save a single donation record
   * @returns true on success, false on failure
   */
  function saveDonation($newcontent, $id) {
		debug_message("store donation $id");
    $this->layer->lockResources("donations");
		return $this->layer->saveOne("donations", $newcontent, $id);
    $this->layer->unlockResources("donations");
  }

  /**
   * Saves our donations data
   * @returns true on success, false on failure
   */
  function saveDonations( $donations ) {
		$this->layer->saveAll("donations", $donations);
    return true;
  }
	
	/**
	 * delete a single donation record
	 */
	function deleteDonation($id) {
		return $this->layer->deleteOne("donations", $id);
	}

  /**
   * add a new channel to our data files
   * @returns id of the new channel on success, false on failure
   */
	function addNewChannel( $channelname ) {
		$channel = array();
		$channel["Name"] = $channelname;
		return $this->saveChannel($channel);
	}

	/**
	 * store a single channel
	 */
	function saveChannel($channel) {

		$this->layer->lockResources( array("channels", "channel_sections", "channel_files", "channel_options", "section_files") );
		$channels = $this->layer->getAllLock("channels", $handle);

		if ( ! isset($channel["ID"]) ) {	
			$lastID = 0;
	
			if ( ! isset($handle) ) {
				global $errstr;
				$errstr = "Couldn't load channels data";
				return false;		
			}
	
			if ( isset($channels) ) {
				foreach ( $channels as $tmp ) {
					if ( $tmp['ID'] > $lastID ) {
						$lastID = $tmp['ID'];
					}
				}
			}

			$channel["ID"] = $lastID + 1;
		}

		if ( !isset($channel['LibraryURL']) ) {
		    $channel['LibraryURL'] = get_base_url() . "library.php?i=" . $channel["ID"];
		}

		if ( !isset($channel['CSSURL']) ) {
		    $channel['CSSURL'] = "default.css";
		}

		if ( !isset($channel['Files']) ) {
	    $channel['Files']=array();
		}
		if ( !isset($channel['Options']) ) {
	    $channel['Options']=array();
			$channel['Options']['Thumbnail']=true;
			$channel['Options']['Title']    =true;
			$channel['Options']['Creator']  =false;
			$channel['Options']['Description']     =false;
			$channel['Options']['Length']   =false;
			$channel['Options']['Published']=false;
			$channel['Options']['Torrent']  =false;
			$channel['Options']['URL']      =false;
			$channel['Options']['Filesize'] =false;
			$channel['Options']['Keywords'] =true;
		}
		if ( !isset($channel['Sections']) ) {
	    $channel['Sections']=array();
			$channel['Sections']['Featured']=array();
			$channel['Sections']['Featured']['Name']='Featured';
			$channel['Sections']['Featured']['Files']=array();
		}
	
		$this->layer->saveOne("channels", $channel, $channel["ID"], $handle);

		$this->layer->unlockResources( array("channels", "channel_sections", "channel_files", "channel_options", "section_files") );
    return $channel["ID"];
	}

 
  /**
   * given an array of files, write it to the filesystem
   */
  function store_files($newcontent) {
		$this->layer->saveAll("files", $newcontent);
		foreach($newcontent as $f) {
			$this->store_file($f);		
		}
  }

	/**
	 * store the data for a single file
	 */
  function store_file($newcontent, $id = "") {
    $this->layer->lockResources( array("files", "channels", "section_files", "channel_files", "channel_options", "file_keywords", "file_people") );
		if ( $id == "" ) {
			$id = $newcontent["ID"];
		}

		$this->layer->saveOne("files", $newcontent, $id);
    $this->layer->unlockResources( array("files", "channels", "section_files", "channel_files", "channel_options", "file_keywords", "file_people") );
  }

  /**
   * delete a user
   * @returns true on success, false on failure
   */
  function deleteUser( $username ) {

		$this->layer->lockResources( array("users") );

		global $data_dir;
		$users = $this->layer->getAllLock("users", $handle);

		if ( count($users) <= 0 ) {
			return true;
		}

		$this->layer->deleteOne("users", $username, $handle);
		$this->layer->unlockResources( array("users") );
    return true;
  }



  /**
   * add a new user
   * @returns true on success, false on failure
   */
  function addNewUser( $username, $password, $email, $isAdmin = false, $isFront = false, &$error) {
    global $settings;
    global $data_dir;

    $username = trim(mb_strtolower( $username ));

		if ( strlen($username) == 0 || $username == "" ) {
				$error = "Please specify a username";
				return false;		
		}

		$this->layer->lockResources( array("users", "newusers") );
		
		$handle2 = NULL;
    $users = $this->layer->getAllLock("users", $handle2);

    if ( isset( $users[$username] ) ) {
      $error = "That username already exists";
      return false;
    }

    foreach ( $users as $user ) {
      if ( isset($user['Email']) && $email == $user['Email'] ) {
        $error = "A user with that email address is already registered";
        return false;
      }
    }

		// if there aren't any users, this person becomes admin by default,
		// and we don't require authorization
		if ( count($users) == 0 ) {
			$settings['RequireRegAuth'] = false;
			$isAdmin = true;
		}
	
		debug_message("addNewUser - lock newusers");
		$newusers = $this->layer->getAllLock("newusers", $handle);
	
		if ( !isset($handle) ) {

			global $errstr;
			if ( isset($errstr) ) {
				$error = $errstr;
			}

			$this->layer->unlockResources( array("users", "newusers") );
			return false;
		}

    $hashlink = $this->userHash( $username, $password, $email );
    $filehash = sha1( $username . $hashlink );
    $newusers[$filehash]['Hash'] = hashpass( $username, $password );
    $newusers[$filehash]['Email'] = $email;
    $newusers[$filehash]['IsAdmin'] = isset($isAdmin) && $isAdmin == true ? 1 : 0;
    $newusers[$filehash]['Created'] = time();

		$result = $this->layer->saveOne("newusers", $newusers[$filehash], $filehash, $handle);
		$this->layer->unlockResources( array("users", "newusers") );

		
		// some sort of error, so stop processing
		if ( $result == false ) {
			global $errstr;
			if ( isset($errstr) ) {
				$error = $errstr;
			}
			return false;
		}
	
		$qs_app = "";
	
		if ( $isFront ) {
			$qs_app="&f=1";
		}
	
		if ( $settings['RequireRegAuth'] && count($users) > 0 && !is_admin() ) {
	
			// cjm - obviously we shouldn't be doing this, but while i'm running the unit tests
			// 100x a day i'm turning off email generation
			global $RUNNING_UNIT_TESTS;
			if ( ! ( isset($RUNNING_UNIT_TESTS) && $RUNNING_UNIT_TESTS == true ) ) {
	
				mail( $email,
				"New Account on " . site_title(),
				"Click below to activate your account:\n" . get_base_url() . "login.php?hash="
				. $hashlink . "&username=" . urlencode( $username ) . $qs_app );
			}
		}
	
		return true;
  }
	
	/**
	 * save a user
	 */
	function saveUser( $u ) {
		if ( ! isset($u["Username"]) ) {
			$u["Username"] = $u["Name"];
		}
		$this->layer->saveOne("users", $u, $u["Username"] );
	}

	/**
	 * generate a user hash and return it
	 * @returns string
	 */
	function userHash( $username, $password, $email ) {
		$username = trim(mb_strtolower( $username ));
		return sha1($username . $password . $email);
	}

  /**
   * authorize a user for access to the website
   * @returns true on success, false on failure
   */
  function authNewUser( $hashlink, $username ) {
	
    global $settings;
    global $data_dir;	
	
	
		$handle = NULL;
		$handle2 = NULL;

    $success = false;

		$name = $username;
    $username = trim(mb_strtolower( $username ));
    $filehash = sha1( $username . $hashlink );

		$this->layer->lockResources( array("users", "newusers") );

		$newusers = $this->layer->getAllLock("newusers", $handle);
		if ( !isset($handle) || $handle == "" ) {
			global $errstr;
			$errstr = "Error: Couldn't open newusers file";
			return false;
		}

    if ( isset( $newusers[$filehash] ) ) {
			$users = $this->layer->getAllLock("users", $handle2);

			if ( !isset($handle2) || $handle2 == "" ) {
				global $errstr;
				$errstr = "Error: Couldn't open users file";
				fclose($handle);
				return false;
			}

      if ( isset( $users[$username] ) ) {
				global $errstr;
				$errstr = "Error: User $username missing";
        return false;
      }


			if ( isset($users) && is_array($users) ) {
				foreach ( $users as $user ) {
					if ( $newusers[$filehash]['Email'] == $user['Email'] ) {
						global $errstr;
						$errstr = "Error: A user with that email address already exists.";
						return false;
					}
				}
			}

	
      $isAdmin = false;
	
      if ( count($users) == 0 || $newusers[$filehash]['IsAdmin'] ) {
        $isAdmin = true;
      }
	
      $pending = false;
	
      if ( !$isAdmin && $settings['RequireRegApproval'] && !is_admin() ) {
        $pending = true;
      }

      $users[$username]['Hash']     =$newusers[$filehash]['Hash'];
      $users[$username]['Name']     =$name;
      $users[$username]['Email']    =$newusers[$filehash]['Email'];
      $users[$username]['IsAdmin']  =$isAdmin;
      $users[$username]['IsPending']=$pending;
      $users[$username]['Created']  =$newusers[$filehash]['Created'];
      $users[$username]['Username'] = $username;
	  
	  	$this->layer->saveOne("users", $users[$username], $username, $handle2);

      $success = true;
    }
		else {
			global $errstr;
			$errstr = "Error: Invalid Hash";
			$success = false;
		}

//		$this->layer->unlockResource("users");

		if ( $success == true ) {
			$this->layer->deleteOne("newusers", $filehash, $handle);
		}

//		$this->layer->unlockResource("newusers");
		$this->layer->unlockResources( array("users", "newusers") );

    return $success;
  }

  /**
   * rename a user
   *
   * NOTE - make sure this doesn't screw up any of our other data
   * @returns true on success, false on failure
   */
  function renameUser( $oldname, $newname ) {

    $users = $this->layer->getAllLock("users", $handle);
		$result = false;

		if ( isset($users[$oldname]) ) {
				
			$users[$newname] = $users[$oldname];

			$users[$newname]['Name'] = $newname;
			$users[$newname]['Username'] = $newname;

			$this->layer->deleteOne("users", $oldname, $handle);
			$this->layer->saveOne("users", $users[$newname], $handle);
				
			$result = true;
		}
		
		$this->layer->unlockResource( "users" );
		return $result;
  }



  /**
   * update user data
   *
   * NOTE - make sure this doesn't screw up any of our other data
   * @returns true on success, false on failure
   */
  function updateUser( $username, $hash, $email, $canAdmin = false, $isPending = true ) {

    global $data_dir;
	
    $user = $this->layer->getOne("users", $username);
    if ( ! $user || count($user) <= 0 ) {
			global $errstr;
			$errstr = "Sorry, that user doesn't exist";
      return false;
    }

    $user['Username'] = $username;
    $user['Hash']     =$hash;
    $user['Email']    =$email;
    $user['IsAdmin']  =$canAdmin;
    $user['IsPending']=$isPending;

		$this->layer->saveOne("users", $user, $username);
  }


  /**
   * perform a BitTorrent announce
	 *
	 * this gets called periodically from a BT client to update the server on its status
   * @returns data to be passed back to the client or NULL on error
   */
	function BTAnnounce( $info_hash, $event, $remote_addr, $port, $left, $numwant ) {

		if ( $this->layer->type() == "MySQL" ) {
      return $this->MySQLBTAnnounce($info_hash, $event, $remote_addr, $port, $left, $numwant);
    }
    else {
      return $this->FlatBTAnnounce($info_hash, $event, $remote_addr, $port, $left, $numwant);
    }

    switch ( $event ) {

      /*    case "started":
      $torrentfile = $this->getTorrentFromHash($info_hash);
      $id = $this->getHashFromFilename($torrentfile);
      $this->recordStartedDownload($id, true);
    case "stopped":
      */

    case "completed":
      $torrentfile = $this->getTorrentFromHash($info_hash);
      $id = $this->getHashFromFilename($torrentfile);
      $this->recordCompletedDownload($id);
      break;
      
    default:
      break;
    }
  }

  function recordStartedDownload($id, $is_torrent = false) {

    error_log("START: $id");

    if ( $is_torrent == true ) {
      $key = "downloading";
    }
    else {
      $key = "downloads";
    }

    $info = $this->layer->getOne("stats", $id, $handle);
    if ( !isset($info[$key]) ) {
      $info[$key] = 0;
    }
    $info[$key]++;
    $this->layer->saveOne("stats", $info, $id, $handle);
  }

  function recordCompletedDownload($id) {
    $info = $this->layer->getOne("stats", $id, $handle);

    if ( !isset($info["downloads"]) ) {
      $info["downloads"] = 0;
    }
    if ( !isset($info["downloading"]) ) {
      $info["downloading"] = 0;;
    }

    $info["downloads"]++;
    $info["downloading"]--;

    if ( $info["downloading"] < 0 ) {
      $info["downloading"] = 0;
    }

    $this->layer->saveOne("stats", $info, $id, $handle);
  }


	function FlatBTAnnounce( $info_hash, $event, $remote_addr, $port, $left, $numwant ) {

		$this->error = '';

		// make sure this is a valid hash
		if ( strlen( $info_hash ) != 40 ) {
			$this->error = 'Invalid info hash';
			return null;
		}

		// make sure the torrent actually exists
		global $data_dir;

		// see if this torrent should be server-shared, and if so, make sure it is running
		$torrentfile = $this->getTorrentFromHash($info_hash);

		if ( !file_exists( $data_dir . '/' . $info_hash ) ) {
			$this->error = 'This torrent is not authorized on this tracker.';
			return null;
		}

		
		global $seeder;
		
		$stats = $this->getStat($info_hash);

		if ( $seeder->enabled() && 
				isset($stats["process id"]) &&
				! file_exists("$data_dir/" . $torrenthash . ".paused") ) {

			// check to see if the pid exists
			// if not, clear it out and restart
			if ( ! is_process_running($stats["process id"]) ) {
				$seeder->spawn($torrentfile);
			}
		}


		// figure out the IP/port of the client
		$peer_ip  = explode( '.', $remote_addr );
		$peer_ip  = pack( "C*", $peer_ip[0], $peer_ip[1], $peer_ip[2], $peer_ip[3] );
		$peer_port = pack( "n*", (int)$port );

		// Generate a number 0-127 based on the minute - this is a bit
		// hackish to say the least, and maybe we should fix in the future
		$time = intval( ( time() % 7680 ) / 60 );
		$int_time = $time;

		// If this is a seeder, set the high bit
		if ( $left == 0 ) {
			$time += 128;
		}

		$time = pack( "C", $time );

		$handle = fopen( $data_dir . '/' . $info_hash, "rb+" );
		flock( $handle, LOCK_EX );
		$peer_num = intval( filesize( $data_dir . '/' . $info_hash ) / 7 );

		if ( $peer_num > 0 ) {
			$data = fread( $handle, $peer_num * 7 );
		}
		else {
			$data = '';
		}

		$peer = array();
		$updated = false;

		// Update the peer
		for ( $i=0; $i < $peer_num; $i++ ) {

			if ( ( $peer_ip . $peer_port ) == substr( $data, $i * 7 + 1, 6 ) ) {

				$updated = true;


				if ( $event != 'stopped' ) {
					$peer[] = $time . $peer_ip . $peer_port;
				}
			} 
			else {

				$peer_seed = join( '', unpack( "C", substr( $data, $i * 7, 1 ) ) );
		
				if ( $peer_seed >= 128 ) {
					$peer_time = $peer_seed - 128;
				}
				else {
					$peer_time = $peer_seed;
				}

				$diff = $int_time - $peer_time;
        if ( $diff < 0 ) // Check for loop around
          $diff += 128;

				// we've heard from the peer in the last 10 minutes, so don't
				// delete them
				if ( $diff < 10 ) {
					$peer[] = substr( $data, $i * 7, 7 );
				}
			}
		}

		// If we don't already have this peer in that database, add it
		if ( $updated == false ) {
			$peer[] = $time . $peer_ip . $peer_port;
		}

		// the number of peers left standing is simply the number of elements in the peer array
		$peer_num = count($peer);

		rewind ( $handle );
		ftruncate( $handle, 0 );
		fwrite( $handle, join( '', $peer ), $peer_num * 7 );
		flock( $handle, LOCK_UN );
		fflush( $handle );
		fclose( $handle );
		clearstatcache();

		$o = '';

		// Fill $o with a list of peers
		if ( $event == 'stopped' || $numwant === 0 ) {
			$o = '';
		}
		else {
			if ( $peer_num > 50 ) {
				$key = array_rand( $peer, 50 );

				foreach ( $key as $val ) {
					$o .= substr( $peer[$val], 1, 6 );
				}
			}
			else {
				for ( $i=0; $i < $peer_num; $i++ ) {
					$o .= substr( $peer[$i], 1, 6 );
				}
			}
		}

    if ($peer_num <= 3) {
      $interval = '30';
    }
    else {
      $interval = '300';
    }

		return 'd8:intervali'.$interval.'e5:peers' . strlen( $o ) . ':' . $o . 'e';
	}


  function MySQLBTAnnounce( $info_hash, $event, $remote_addr, $port, $left, $numwant ) {
  	$this->error = '';

    if ( strlen( $info_hash ) != 40 ) {
      $this->error = 'Invalid info hash';
      return null;
    }

    $peer_ip  =explode( '.', $remote_addr );
    $peer_ip  =pack( "C*", $peer_ip[0], $peer_ip[1], $peer_ip[2], $peer_ip[3] );
    $peer_port=pack( "n*", (int)$port );
    $seeder   =( $left == 0 ) ? '1' : '0';

    if ( !$this->torrentExists( $info_hash ) ) {
      $this->error = 'This torrent is not authorized on this tracker.';
      return null;
    }

    if ( $event == 'stopped' ) {
      do_query ( "DELETE FROM " . $this->layer->prefix . "peers 
                  WHERE info_hash='" . mysql_escape_string($info_hash ) . "' 
                  AND ip='" . mysql_escape_string( $peer_ip ) . "' 
                  AND port='" . mysql_escape_string( $peer_port ) . "'" );
		}
    else {
      do_query ( "REPLACE INTO " . $this->layer->prefix . "peers (info_hash,ip,port,seeder,time) VALUES ('"
		    . mysql_escape_string( $info_hash )
		    . "', '" . mysql_escape_string( $peer_ip )
		    . "','" . mysql_escape_string( $peer_port ) . "','" . mysql_escape_string( $seeder )
		    . "',NOW())" );
		}

    $peer_num = 0;


    do_query( "DELETE FROM " . $this->layer->prefix . "peers 
               WHERE time < DATE_SUB(NOW(), INTERVAL 600 SECOND)");

    $o = '';

    // Fill $o with a list of peers
    if ( $event == 'stopped' || $numwant === 0 ) {
      $o = '';
    }
    else {
      $result = do_query( "SELECT CONCAT(ip,port) as out 
                         FROM " . $this->layer->prefix . "peers 
                         WHERE info_hash='" . mysql_escape_string( $info_hash ) . "' 
                         ORDER BY RAND() LIMIT 50" );

      while ( $row = mysql_fetch_array( $result ) ) {
				$peer_num++;
				$o .= $row[0];
      }
    }


    if ($peer_num <= 3) {
      $interval = '30';
		}
    else {
      $interval = '300';
		}

    return 'd8:intervali'.$interval.'e5:peers' . strlen( $o ) . ':' . $o . 'e';
  }


	/**
	 * get the stats for the given torrent
	 * @return array of stats
	 */
  function getStat( $info_hash ) {

		$complete = 0;
		$incomplete = 0;

    if ( $this->layer->type() == "MySQL" ) {
      do_query( "DELETE FROM " . $this->layer->prefix . "peers WHERE time < DATE_SUB(NOW(), INTERVAL 600 SECOND)");
      
      $query = do_query("SELECT COUNT(*) FROM " . $this->layer->prefix . "peers WHERE info_hash='" . 
                           mysql_escape_string($info_hash) . "'" );
      
      $row = mysql_fetch_array($query);
      $total = $row[0];
      
      $query = do_query("SELECT COUNT(*) FROM " . $this->layer->prefix . "peers WHERE info_hash='" . 
                           mysql_escape_string( $info_hash ) . "' AND seeder = 1" );
      
      $row = mysql_fetch_array($query);
      
      $complete = $row[0];
      $incomplete = $total - $complete;
      
    }
    else {
		
      global $data_dir;

      $time = intval( ( time() % 7680 ) / 60 );
      $int_time = $time;

      if ( file_exists($data_dir . '/' . $info_hash) && filesize($data_dir . '/' . $info_hash) > 0 ) {

        $handle = fopen(  $data_dir . '/' . $info_hash, "rb" );
        flock( $handle, LOCK_EX );
        
        $size = filesize(  $data_dir . '/' . $info_hash );
        
        if ( $size > 0 ) {
          $x = fread( $handle, $size );
          flock( $handle, LOCK_UN );
          fclose ( $handle );
          $no_peers = intval( strlen( $x ) / 7 );

          for ( $j = 0; $j < $no_peers; $j++ ) {
            $t_peer_seed = join( '', unpack( "C", substr( $x, $j * 7, 1 ) ) );
            
            if ( $t_peer_seed >= 128 ) {
              $peer_time = $t_peer_seed - 128;
            }
            else {
              $peer_time = $t_peer_seed;
            }
            
            $diff = $int_time - $peer_time;
            if ($diff < 0) // Check for loop around
              $diff += 128;
            
            // we've heard from the peer in the last 10 minutes, so count it
            if ( $diff < 10 ) {
              if ( $t_peer_seed == $peer_time )
                $incomplete++;
              else
                $complete++;
            }
            
          } // for

        } // if ( size > 0 )

      }
      // if the infohash doesn't exist, that means we're sharing a torrent that is being announced
      // on another server, so parse the stats from our .status file
      else if ( file_exists($data_dir . '/' . $info_hash . '.status') ) {
        $status = file_get_contents( $data_dir . '/' . $info_hash . '.status');

        if ( preg_match("/seed status: ([0-9]+) distributed copies/", $status, $vals) ) {
          $complete = $vals[1] + 1;
        }
        else {
          preg_match("/seed status: ([0-9]+) seen now/", $status, $vals);
          $complete = isset($vals[1]) ? $vals[1] : "??";
        }

        preg_match("/peer status: ([0-9]+) seen now/", $status, $vals);
        $incomplete = isset($vals[1]) ? $vals[1] : "??";
      }

    } // else

    return array (
                  "hash"		 => $info_hash,
                  "complete"   => $complete,
                  "incomplete" => $incomplete
                  );    
    
	}
		
	/**
	 * figure out what the hash is for the given filename
	 */
	function getHashFromTorrent( $filename ) {

    if ( $this->layer->type() == "MySQL" ) {
      $result = do_query( "SELECT info_hash from " . $this->layer->prefix . "torrents 
                               WHERE filename = '" . mysql_escape_string($filename) . "'" );

      $tmp = mysql_fetch_array( $result );
      return $tmp["info_hash"];
    }
    else {
      $tmp = $this->getTorrent( $filename );
      return $tmp["sha1"];
    }
	}

	/** 
	 * given a torrent's hash, figure out what torrent it is
	 */
	function getTorrentFromHash($hash) {

		$torrents = $this->getTorrentList();

		foreach($torrents as $t) {
				$tmp = $this->getTorrent( $t );
				if ( isset($tmp["info"]["name"]) && $hash == $tmp["sha1"] ) {
					return $tmp["info"]["name"];
				}
		}
		
		return null;
	}

	/**
	 * get a list of torrents that are currently in the system
	 */
	function getTorrentList() {

    if ( $this->layer->type() == "MySQL" ) {
      $list = array();
      $result = do_query( "SELECT filename from " . $this->layer->prefix . "torrents" );
      
      while ( $row = mysql_fetch_array( $result ) ) {
        $list[]=$row[0];
      }
      
      return $list;
    }
    else {
      $list = array();
      $times = array();
      global $torrents_dir;
      
      $handle = opendir( $torrents_dir );
      while ( false !== ( $torrentfile=readdir( $handle )) ) {
        if ( $torrentfile != '.' && 
             $torrentfile != '..' && 
             endsWith($torrentfile, ".torrent") ) {
          $list[] = $torrentfile;
          $times[] = $this->getTorrentDate( $torrentfile );
        } // if
      } // while
      
      if ( count( $list ) > 0 ) {
        array_multisort( $times, SORT_DESC, $list );
      }

      return $list;
		}

  }

	/**
	 * get the torrent data for the specified file
	 */
  function getTorrent( $filename ) {
    return bdecode( $this->getRawTorrent( $filename ) );
  }
	
	/**
	 * save a torrent to the filesystem
   * todo - add mysql code here
	 */
	function saveTorrent( $filename, $data ) {
		global $torrents_dir;
    
		$handle = fopen( "$torrents_dir/$filename", "a+b");
     
    fseek($handle,0);
    flock($handle, LOCK_EX);
    ftruncate($handle,0);
    fseek($handle,0);
    fwrite($handle,bencode($data));
    fclose($handle);		
	}


	/**
	 * get the raw torrent file
	 */
  function getRawTorrent( $filename ) {

    if ( $this->layer->type() == "MySQL" ) {
      $result = do_query( "SELECT raw_data FROM " . $this->layer->prefix . "torrents 
                              WHERE filename='" . 
                             mysql_escape_string($filename ) . "'" );
      
      if ( mysql_num_rows( $result ) > 0 ) {
        $row=mysql_fetch_row( $result );
        return $row[0];
      }
      
    }
    else {
      global $torrents_dir;
      
      if ( file_exists( $torrents_dir . "/" . $filename ) ) {
        return file_get_contents( $torrents_dir . "/" . $filename );
      }
      
    }

    return null;

  }

	/** 
	 * figure out the creation date of the torrent
	 */
  function getTorrentDate( $filename ) {
    global $torrents_dir;
    return filectime( $torrents_dir . '/' . $filename );
  }

	/**
	 * does the specified torrent exist?
	 */
  function torrentExists( $info_hash ) {

    if ( $this->layer->type() == "MySQL" ) {
      $result =do_query( "SELECT COUNT(*) FROM " . 
                            $this->layer->prefix . "torrents WHERE info_hash='" . 
                            mysql_escape_string( $info_hash ) . "'" );
      $row=mysql_fetch_row( $result );
      return $row[0] > 0;
    }
    else {
      global $data_dir;
      return file_exists(  $data_dir . '/' . $info_hash );
    }
  }


  /**
   * load a list of peers from the filesystem, for the given hash.  if prune is true,
   * peers that we haven't heard from in 30 minutes get removed from the list
   *
   * @returns list of peers for a torrent
   */
  function getTorrentDetails( $info_hash, $prune = true ) {

    if ( $this->layer->type() == "MySQL" ) {
      $peers=array();

      $now   =time();
      $result=do_query(
                          "SELECT ip, port, UNIX_TIMESTAMP(time) AS time,	 if (seeder,'seeder','leecher') AS what FROM " . 
                          $this->layer->prefix . "peers WHERE info_hash = '" . mysql_escape_string( $info_hash )
                          . "'" );
      
      while ( $row=mysql_fetch_array( $result ) ) {
        $ip  = unpack( "C*", $row['ip'] );
        $ip  =$ip[1] . '.' . $ip[2] . '.' . $ip[3] . '.*';
        $port=join( '', unpack( "n*", $row['port'] ) );
        
        $peers[]=array
          (
           "ip"	    => $ip,
           "what" => $row['what'],
           "port" => $port,
           "time" => number_format( (int)( ( $now - $row['time'] ) / 60 ) )
           );
        
      } // while
      
      return $peers;
    }
    else {

      $peers = array();
      global $data_dir;
    
      $handle=fopen(  $data_dir . '/' . $info_hash, "rb+" );
      flock( $handle, LOCK_EX );
      
      if ( filesize(  $data_dir . '/' . $info_hash ) > 0 ) {
        $x = fread( $handle, filesize(  $data_dir . '/' . $info_hash ) );
      }
      else {
        $x='';
      }
      
      flock( $handle, LOCK_UN );
      fclose ( $handle );
      $no_peers = intval( strlen( $x ) / 7 );
      
      for ( $j=0; $j < $no_peers; $j++ ) {
        $ip         = unpack( "C*", substr( $x, $j * 7 + 1, 4 ) );
        
        // cjm - get whole ip instead of just 3/4
        $ip         =$ip[1] . '.' . $ip[2] . '.' . $ip[3] . '.' . $ip[4];
        //			$ip         =$ip[1] . '.' . $ip[2] . '.' . $ip[3] . '.*';
        $port       =join( '', unpack( "n*", substr( $x, $j * 7 + 5, 2 ) ) );
        $t_peer_seed=join( '', unpack( "C", substr( $x, $j * 7, 1 ) ) );
        
        if ( $t_peer_seed >= 128 ) {
          $what      ='seeder';
          $t_time = $t_peer_seed - 128;
        }
        else {
          $what      ='leecher';
          $t_time = $t_peer_seed;
        }
        
        // figure out the current time
        $time = intval( ( time() % 7680 ) / 60 );
        
        // we've heard from this peer in 30 minutes or less, so add them to the list
        if ( $prune == false || $time - $t_time <= 30 ) {
          
          $peers[] = array(
                           "ip"       => $ip,
                           "what" => $what,
                           "port" => $port,
                           "time" => number_format( $time - $t_time )
                           );
        }
        
      }

      return $peers;
    }
  }

	/**
	 * determine if the given hash is a valid one for posting torrent
	 * @returns true/false
	 */
  function isValidAuthHash( $username, $hash ) {

    global $data_dir;

    debug_message("isValidAuthHash");

		if ( file_exists( $data_dir . '/hash' ) ) {

      debug_message("isValidAuthHash - check for hash");
    
			$hashes = bdecode( file_get_contents( $data_dir . '/hash' ) );
     // foreach($hashes as $h => $t) {
     //   debug_message("AuthHash: $h $t");
     // }

      debug_message("AuthHash: check for $username $hash - " . sha1($username . $hash) );
      debug_message("AuthHash: " . $hashes[sha1( $username . $hash )]);

			return ( isset( $hashes[sha1( $username . $hash )] ) && 
							( $hashes[sha1( $username . $hash )] > ( time() - 3600 ) ) 
							);
		}
		
		return false;
  }

	/**
	 * generate a hash for the given user/password-hash.  will be sent along with a torrent being posted
	 *
	 * note - we also cleanup old hashes in this function
	 */
  function getAuthHash( $username, $passhash ) {
    $hash = md5( $username . microtime() . rand() . $passhash );
    $this->addAuthHash($username, $hash);
    return $hash;
  }

  function addAuthHash( $username, $hash ) {
    global $data_dir;

    $contents = '';

    $handle = fopen(  $data_dir . '/hash', "ab+" );
    fseek( $handle, 0 );
    flock( $handle, LOCK_EX );

    while ( !feof( $handle ) ) {
      $contents .= fread( $handle, 8192 );
    }

    $hashes = bdecode( $contents );

    if ( ! is_array( $hashes ) )
      $hashes = array();

    $hashval = sha1( $username . $hash );
    $hashes[$hashval] = time();

	  $this->clearOldAuthHashes($hashes);

    ftruncate( $handle, 0 );
    fseek( $handle, 0 );
    fwrite( $handle, bencode( $hashes ) );

    fclose ( $handle );
    return $hashval;
  }

	/**
	 * drop a auth hash which has been used to post a torrent, and write some info about the torrent
	 * into a file using the hash as the filename.
	 *
	 * note - we also cleanup old hashes in this function
	 */
  function dropAuthHash( $username, $hash, $torrent ) {
    $contents  = '';

    global $data_dir;

		// create a file containing the hash and write the torrent name to it so
		// we can link them up later
    $handle = fopen(  $data_dir . '/' . $hash, "wb+" );
    fwrite( $handle, $torrent );
    fclose ( $handle );

		// remove the hash from our list of auth hashes
    $handle = fopen(  $data_dir . '/hash', "a+b" );
    fseek( $handle, 0 );
    flock( $handle, LOCK_EX );

    while ( !feof( $handle ) ) {
      $contents .= fread( $handle, 8192 );
    }

    $hashes = bdecode( $contents );
    unset ( $hashes[sha1( $username . $hash )] );

		// clear out any stale hashes while we're at it
    $this->clearOldAuthHashes( $hashes );

    ftruncate( $handle, 0 );
    fseek( $handle, 0 );
    fwrite( $handle, bencode( $hashes ) );
    fclose ( $handle );
  }


	/**
	 * iterate through an array of auth hashes and clear out any that are more than
	 * an hour old
	 */ 
  function clearOldAuthHashes( &$hashes ) {

    $now = time();

    foreach ( $hashes as $hash => $stamp ) {
			//Hash was created more than 1 hour ago
      if ( $stamp < $now - 3600 ) {
        unset ( $hashes[$hash] );
			}
    }
  }

  /**
   * Sends the location of this feed to BlogTorrent.com periodically
   * @deprecated not in use?
   */
  function phoneHome() {
    global $settings;
    global $data_dir;

    //Phone home if settings have been saved, the box is checked, and we
    //haven't phoned home in a week
    if ( $this->settingsExist() && $settings['Ping'] ) {
      if ( file_exists(  $data_dir . '/phonelock' ) ) {
        $stat    =stat(  $data_dir . '/phonelock' );
        $doit=$stat[9] < ( time() - 604800 ); //9 is mtime
      }
      else {
        $doit = true;
      }
			
      if ( $doit ) {
        $handle = fopen(  $data_dir . '/phonelock', 'wb' );
        fclose ( $handle );
        file_get_contents ( 'http://www.blogtorrent.com/register.php?server='
                            . htmlspecialchars( get_base_url() )
                            . 'rss.php&version=' . get_version());
      }
			
      return $doit;
    }
  }


  /**
   * add a torrent to the tracker
   */
  function addTorrentToTracker( $torrent ) {

    global $seeder;
    global $settings;
    global $perm_level;
    
    global $data_dir;
    global $torrents_dir;
    
    debug_message("addTorrentToTracker");

    $rawTorrent = file_get_contents(  "$torrents_dir/$torrent" );
    
    if ( !file_exists( "$torrents_dir/$torrent" ) ) {
      debug_message("addTorrentToTracker: torrent doesn't exist!");
      return false;
    }
    else {
      debug_message("addTorrentToTracker: get hash");
      
      chmod( "$torrents_dir/$torrent", 0777);
      
      $info_hash = $this->getHashFromTorrent( $torrent );

      if ( !file_exists(  $data_dir . '/' . $info_hash ) ) {
        $handle = fopen(  $data_dir . '/' . $info_hash, "wb" );
        //        fwrite($handle, $torrent);
        fclose ( $handle );
      }
    }

    
    if ( $this->layer->type() == "MySQL" ) {

      debug_message("addtorrent: here");

      $data = bdecode( $rawTorrent );
      
      $sql = "INSERT INTO " . $this->layer->prefix . "torrents (info_hash, filename, raw_data) 
										VALUES (
											'" . mysql_escape_string( $data['sha1'] ) . "',
											'" . mysql_escape_string( $torrent ) . "',
											'" . mysql_escape_string( $rawTorrent ) . "')";
      do_query ( $sql );
      
    }
    
    if ( $seeder->enabled() && $settings["sharing_auto"] ) {
      $seeder->spawn( $torrent );
    }
  }


	/**
	 * delete the given torrent from the filesystem
	 */	
  function deleteTorrent( $torrent ) {
    global $seeder;

    if ( $seeder->enabled() ) {
      $seeder->stop( $torrent );
		}
		
		if ( $this->layer->type() == "MySQL" ) {

			$result = do_query( "SELECT info_hash FROM " . $this->layer->prefix . "torrents WHERE filename='" . 
				mysql_escape_string($torrent ) . "'" );
	
			if ( mysql_num_rows( $result ) > 0 ) {
				$row = mysql_fetch_row( $result );
				$info_hash=$row[0];
	
				do_query ( "DELETE FROM " . $this->layer->prefix . "peers WHERE info_hash='" . 
					mysql_escape_string( $info_hash ) . "'" );
				do_query ( "DELETE FROM " . $this->layer->prefix . "torrents WHERE info_hash='" . 
					mysql_escape_string( $info_hash ) . "'" );
			}
		}

    global $data_dir;
    global $torrents_dir;

    $file = $this->getHashFromTorrent( $torrent );
		if ( file_exists("$torrents_dir/$torrent") ) {
	    unlink_file ( "$torrents_dir/$torrent" );
		}
		
		if ( file_exists("$data_dir/$file") ) {
	    unlink_file ( "$data_dir/$file" );
		}
  }


  /**
	 * Converts a zipfile into a serialized PHP object
   * Normally, we ship Broadcast Machine Helper with a serialized object containing
   * the Mac client, but if it's not there, we can make it on the fly
   * using this function
   */
  function createZipObject( $zipfile ) {
    $zipobj = new zipfile();
    $origzip = @zip_open( $zipfile );

    if ( $origzip ) {
      while ( $entry = zip_read( $origzip ) ) {
        $name = zip_entry_name( $entry );
        $size = zip_entry_filesize( $entry );
        
        if ( $size == 0 )
          $zipobj->add_dir( $name );
        else {
          zip_entry_open( $origzip, $entry );
          $data = zip_entry_read( $entry, $size );
          zip_entry_close ( $entry );
          $zipobj->add_file( $data, $name, 9 );
        }
      }
      
      return serialize( $zipobj );
    }
    else {
      return null;
    }
  }

  /**
   * display a message to help the user do whatever is required to setup BM
   */
  function setupHelpMessage() {
    $output = <<<EOD
      <div class="wrap">
      <h2 class="page_name">One Final Step...</h2>
      <div class="section">

      <p>You need to create the data directories for Broadcast Machine.</p>
      <p><em>Once you've completed these steps, reload this page to continue.</em></p>

<div class="section_header">If you use graphical FTP</div>

<p>Create folders in your Broadcast Machine directory named "torrents", "data", "publish", "thumbnails" and "text".  
Then select each folder, view its permissions, and make sure all the checkboxes (readable, writable, 
executable) are checked.</p>

<div class="section_header">If you use command line FTP</div>

<p>Log in and type the following:</p>
<pre>
EOD;
#'

	$output.="cd " . preg_replace( '|^(.*[\\/]).*$|', '\\1', $_SERVER['SCRIPT_FILENAME'] );
	$output	.=<<<EOD

mkdir data
mkdir torrents
mkdir publish
mkdir text
mkdir thumbnails
chmod 777 data
chmod 777 torrents
chmod 777 publish
chmod 777 text
chmod 777 thumbnails
</pre>

<p><em>Once you've completed these steps, reload this page to continue.</em></p>
<div class="section_header">If you want Broadcast Machine to do it for you:</div>
<p>Specify your FTP username and password here, and Broadcast Machine will FTP into your server, 
create the directories and set the permissions for you. You need to know the 'root' address for 
your Broadcast Machine FTP address, which could be something like "public_html/bm/" or "httdocs/bm"
</p>
<p>This might take a few minutes, please be patient.</p>

<form method="POST" action="set_perms.php">
     username: <input type="text" name="username" size="10" /><br />
     password: <input type="password" name="password" size="10" /><br />
     ftp root: <input type="text" name="ftproot" size="50" /><br />
     <input type="submit" value="Set Perms" />
</form>

<br />
<p>Note: giving the directories "777" permissions will allow anyone on the server to full access those directories. If you share a server with others, they may be able to tamper with you Broadcast Machine data files if you use these settings. There may be other settings more appropriate for your server. <b>Please, contact your system administrator if you have any questions about permissions.</b></p>

</div>
</div>
EOD;
#'
    print $output;
  }

  function setupHelperMessage() {

		$dest = preg_replace( '|^(.*[\\/]).*$|', '\\1', $_SERVER['SCRIPT_FILENAME'] );

    $output = <<<EOD
      <div class="wrap">
      <h2 class="page_name">One Final Step...</h2>
      <div class="section">

      <p>You are missing the Broadcast Machine upload helper.</p>
      <p><em>Once you've completed these steps, reload this page to continue.</em></p>

<div class="section_header">Uploading the Helper Files</div>

<p>Please upload the files 'nsisinstaller.exe' and 'macclient.obj' to the $dest directory of your webserver</p>
EOD;
#'
    print $output;

  }


  /**
	 * try and setup our Mac/PC helper files, and return true/false according to our success
	 */
	function setupHelpers() {
    global $data_dir;

    if ( ( !file_exists( 'macclient.obj' )) && ( !file_exists(  $data_dir . '/macclient.obj' )) ) {
      $data = $this->createZipObject(
				   preg_replace( '|^(.*[\\/]).*$|', '\\1',
						 $_SERVER['SCRIPT_FILENAME'] ) . 'BlogTorrentMac.zip' );

      if ( is_null( $data ) ) {
 				return false;
			}
				
      $file = fopen(  $data_dir . '/macclient.obj', 'wb' );
      fwrite( $file, $data );
      fclose ( $file );
    }

    if ( ( !file_exists( 'nsisinstaller.exe' )) && ( !file_exists(  $data_dir . '/nsisinstaller.exe' )) ) {
			return false;		
		}

		return true;
	}

} // DataStore


/******************************************************************
 *  DATASTORE HOOKS
 *****************************************************************/

function PreDeleteFile($id, $handle = NULL) {
	global $store;

	$file = $store->getFile($id, $handle);

	if ( is_local_file($file["URL"]) ) {

		$filename = local_filename($file["URL"]);

		if ($filename != "") {
			if ( is_local_torrent($file["URL"]) ) {
				global $seeder;
				
				// stop the seeder process and delete any files
				// related to the torrent
				$seeder->stop($filename, true);
				$store->deleteTorrent($filename);
			}

			if ( file_exists("torrents/" . $filename) ) {
				unlink_file("torrents/" . $filename);
			}
		}
	} // if is_local_file

	// remove this file from any donations	
	if ( isset($file['donation_id']) ) {
		$donation_id = $file['donation_id'];
		$store->removeFileFromDonation($id, $donation_id);
	}

}

function PostDeleteFile($id) {

	global $store;

	//
	// update our channels data
	//
	$channels = $store->getAllChannels();
	
	// keep track of which RSS feeds need to be updated
	$update_rss = array();

	foreach ($channels as $channel) {
		$keys = array_keys($channel['Files']);

		foreach ($keys as $key) {
			$file = $channel['Files'][$key];
			if ($file[0] == $id) {
				$update_rss[] = $channel['ID'];
				unset($channel['Files'][$key]);
			}
		}

		if (is_array($channel['Sections'])) {
			$sections = array_keys($channel['Sections']);

			foreach ($sections as $section) {
				if (is_array($section['Files'])) {
					$keys = array_keys($section['Files']);
					foreach ($keys as $key) {
						$file = $channel['Files'][$key];
						if ($file == $id) {
							unset($channel['Sections'][$section]['Files'][$key]);
						}
					}
				}
			}
		}

		$channels[$channel['ID']] = $channel;
		$store->saveChannel($channel);
	}

	foreach ($update_rss as $channelID) {
		makeChannelRss($channelID, false);
	}

	makeChannelRss("ALL", false);

}

function FlatGetChannelHook(&$c) {
	if ( isset($c["Options"]["Desc"]) ) {
		$c["Options"]["Description"] = $c["Options"]["Desc"];
		unset($c["Options"]["Desc"]);
	}
	if ( isset($c["Desc"]) ) {
		$c["Description"] = $c["Desc"];
    unset($c["Desc"]);
	}
}

function FileHook(&$f) {
	if ( isset($f["Desc"]) ) {
		$f["Description"] = $f["Desc"];
		unset($f["Desc"]);
	}

}

function MySQLFileHook(&$f) {
	if ( isset($f["Desc"]) ) {
		$f["Description"] = $f["Desc"];
		unset($f["Desc"]);
	}

	$f["Keywords"] = array();
	$f["People"] = array();

	global $store;
	
	// get keywords
	$keys = $store->layer->getByKey("file_keywords", $f["ID"]);

	foreach( $keys as $num => $k ) {
    if ( trim($k["word"]) != "" ) {
      $f["Keywords"][] = trim($k["word"]);
    }
	}

	// get people
	$peeps = $store->layer->getByKey("file_people", $f["ID"]);
	foreach( $peeps as $p ) {
		$f["People"][] = array( $p["name"], $p["role"] );
	}

	return $f;
}

function MySQLGetChannelHook(&$c) {

	global $store;

	$qarr = $store->layer->getTableQueries("channel_options");		
	$option_sql = $qarr["select"];

	$qarr = $store->layer->getTableQueries("channel_sections");
	$section_sql = $qarr["select"];

	$qarr = $store->layer->getTableQueries("section_files");
	$sf_sql = $qarr["select"];

	$sql = str_replace("%key", $c["ID"], $option_sql);
	$result = do_query( $sql );

	while ( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) ) {
		$c["Options"] = array();
		foreach($row as $key => $val) {
			$c["Options"][$key] = $val;
		}
	}	

	$sql = str_replace("%key", $c["ID"], $section_sql);
	$result = do_query( $sql );

	while ( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) ) {
		$c["Sections"][ $row["Name"] ]["Name"] = $row["Name"];
		$c["Sections"][ $row["Name"] ]["Files"] = array();

		// section_files
		$sql = "SELECT * FROM " . $store->layer->prefix . "section_files WHERE 
			channel_id = '" . $c["ID"] . "' AND 
			Name = '" . mysql_escape_string( $row["Name"] ) . "'";
		$result2 = do_query( $sql );
		while ( $row2 = mysql_fetch_array( $result2, MYSQL_ASSOC ) ) {
			$c["Sections"][ $row["Name"] ]["Files"][] = $row2["hash"];
		} // while ($row2)
	} // while ($row)

	$sql = "SELECT * FROM " . $store->layer->prefix . "channel_files WHERE 
		channel_id = '" . $c["ID"] . "'";
	$result2 = do_query( $sql );

	$c["Files"] = array();
	while ( $row2 = mysql_fetch_array( $result2, MYSQL_ASSOC ) ) {
		$c["Files"][] = array( 0 => $row2["hash"], 1 => $row2["channel_id"] );
	} // while ($row2)

	return $c;
}

function MySQLPreSaveChannelHook(&$channel) {
	global $store;

	// clear out old files
	$tmp = array();
	$do_query = false;
	foreach( $channel["Files"] as $f ) {
		$tmp[] = "'" . mysql_escape_string($f[0]) . "'";
		$do_query = true;
	}

	if ( $do_query == true ) {
		$sql = "DELETE FROM " . $store->layer->prefix . "channel_files WHERE channel_id = '" . $channel["ID"] ."' AND hash NOT IN (" . implode(",", $tmp) . ")";
		do_query($sql);
	}

	$sect_temp = array();

	foreach( $channel["Sections"] as $s ) {

		$sect_tmp[] = "'" . mysql_escape_string($s["Name"]) . "'";

		// delete section files
		$tmp = array();
		$do_query = false;
		foreach($s["Files"] as $f) {
			$tmp[] = "'" . mysql_escape_string($f) . "'";
			$do_query = true;
		}

		if ( $do_query == true ) {
			$sql = "DELETE FROM " . $store->layer->prefix . 
				"section_files WHERE hash NOT IN (" . implode(",", $tmp) . ")
				AND channel_id = '" . $channel["ID"] . "' AND
					Name = '" . mysql_escape_string($s["Name"]) . "'";
			do_query( $sql );
		}
	}	

	// delete section files from any section that we tossed
	$sql = "DELETE FROM " . $store->layer->prefix . 
		"section_files WHERE channel_id = '" . $channel["ID"] . "' AND
		Name NOT IN (" . implode(",", $sect_tmp) . ")";
	do_query( $sql );
	
	$sql = "DELETE FROM " . $store->layer->prefix . 
		"channel_sections WHERE channel_id = '" . $channel["ID"] . "' AND
		Name NOT IN (" . implode(",", $sect_tmp) . ")";
	do_query( $sql );

	
	// clear out old section files
	$tmp = array();
	foreach( $channel["Files"] as $f ) {
		$tmp[] = "'" . mysql_escape_string($f[0]) . "'";
	}

	$sql = "DELETE FROM " . $store->layer->prefix . "channel_files 
          WHERE channel_id = '" . $channel["ID"] . "' 
          AND hash NOT IN (" . implode(",", $tmp) . ")";
	do_query( $sql );
}

function MySQLSaveChannelHook(&$channel) {

	global $store;

	foreach( $channel["Files"] as $f ) {
		$sql = "REPLACE INTO " . $store->layer->prefix . "channel_files 
			SET channel_id = " . $channel["ID"] . ", 
			hash = '" . mysql_escape_string($f["0"]) . "', 
			thetime = '" . mysql_escape_string($f["1"]) . "'";
		do_query( $sql );
	}

	// store options
//	$store->layer->saveOne("channel_options", $channel["Options"], $channel["ID"]);
	$qarr = $store->layer->getTableQueries("channel_options");
	$query = $qarr["insert"];
	$channel["Options"]["ID"] = $channel["ID"];
	$tmp = $store->layer->prepareForMySQL($channel["Options"]);
	$sql = str_replace("%vals", $tmp, $query);
	do_query( $sql );

	$qarr = $store->layer->getTableQueries("channel_sections");
	$query = $qarr["insert"];

	$qarr = $store->layer->getTableQueries("section_files");
	$sf_sql = $qarr["insert"];

	// store sections
	foreach( $channel["Sections"] as $s ) {
		$data = "channel_id = '" . $channel["ID"] . "', 
			Name = '" . mysql_escape_string($s["Name"]) . "'";
		$sql = str_replace("%vals", $data, $query);
		do_query( $sql );

		// store section files
		foreach($s["Files"] as $f) {
			$data = "channel_id = '" . $channel["ID"] . "', 
				Name = '" . mysql_escape_string($s["Name"]) . "', 
				hash = '" . mysql_escape_string($f) . "'";

			$sql = str_replace("%vals", $data, $sf_sql);
			do_query( $sql );
		}
	}	
}

function MySQLDeleteChannelHook($id) {
	$sql = "DELETE FROM " . $store->layer->prefix . "channel_files WHERE channel_id = $id";
	do_query($sql);

	$sql = "DELETE FROM " . $store->layer->prefix . "section_files WHERE channel_id = $id";
	do_query($sql);

	$sql = "DELETE FROM " . $store->layer->prefix . "channel_sections WHERE channel_id = $id";
	do_query($sql);

	$sql = "DELETE FROM " . $store->layer->prefix . "channel_options WHERE channel_id = $id";
	do_query($sql);
}

function MySQLGetDonationHook(&$d) {

	global $store;

	$qarr = $store->layer->getTableQueries("donation_files");		
	$sql = $qarr["select"];

	$sql = str_replace("%key", $d["id"], $sql);
	$result = do_query( $sql );

  $d["Files"] = array();
  if ( $result ) {
    while ( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) ) {
      $d["Files"][$row["hash"]] = 1;
    }	
  }

	return $d;
}


function MySQLPreSaveFileHook(&$f) {

  //
	// clear out old keywords
  //
	$tmp = array();
	$do_query = false;

	foreach( $f["Keywords"] as $num => $kw ) {
		$tmp[] = "'" . mysql_escape_string($kw) . "'";
		$do_query = true;
	}

	if ( $do_query == true ) {
    global $store;
		$sql = "DELETE FROM " . $store->layer->prefix . "file_keywords 
            WHERE ID = '" . $f["ID"] ."' AND 
            word NOT IN (" . implode(",", $tmp) . ")";
		do_query($sql);
	}


  //
  // delete any people that were removed
  //
	$tmp = array();
	$do_query = false;

	foreach( $f["People"] as $num => $p ) {
		$tmp[] = "'" . mysql_escape_string($p['0']) . "'";
		$do_query = true;
	}

	if ( $do_query == true ) {
		$sql = "DELETE FROM " . $store->layer->prefix . "file_people
            WHERE ID = '" . $f["ID"] ."' AND 
            name NOT IN (" . implode(",", $tmp) . ")";
		do_query($sql);
	}


}


function MySQLSaveFileHook(&$f) {
  global $store;
		
  $qarr = $store->layer->getTableQueries("file_people");
  $people_sql = $qarr["insert"];
		
  $qarr = $store->layer->getTableQueries("file_keywords");
  $kw_sql = $qarr["insert"];
		
  // desc is a reserved word in SQL, so lets not be using that
  if ( isset($f["Desc"]) ) {
    $f["Description"] = $f["Desc"];
    unset($f["Desc"]);
  }
  
  /*  $data = $store->layer->prepareForMySQL($f);
      
  $sql = str_replace("%vals", $data, $query);
  do_query( $sql );
  */
  
  foreach($f["People"] as $p) {
    $tmp["Name"] = trim($p[0]);
    $tmp["Role"] = trim($p[1]);
    $tmp["ID"] = $f["ID"];
    
    if ( $tmp["Name"] != "" ) {
      $data = $store->layer->prepareForMySQL($tmp);
      $sql = str_replace("%vals", $data, $people_sql);
      do_query( $sql );
    }
  }

  foreach($f["Keywords"] as $num => $kw) {
    $kw = trim($kw);
    if ( $kw != "" ) {
      $sql = "REPLACE INTO " . $store->layer->prefix . "file_keywords (id, word) 
								VALUES ('" . mysql_escape_string($f["ID"]) . "', 
								'" . mysql_escape_string($kw) . "')";
    
    
      do_query( $sql );
    }
  } 

  foreach($f["post_channels"] as $num => $channel_id) {
    $sql = "REPLACE INTO " . $store->layer->prefix . "channel_files (channel_id, hash, thetime) 
								VALUES ('" . mysql_escape_string($channel_id) . "', 
								'" . mysql_escape_string($f["ID"]) . "',
								'" . mysql_escape_string($f["Publishdate"]) . ")";
    
    do_query( $sql );   
  }

} // MySQLSaveFileHook


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>