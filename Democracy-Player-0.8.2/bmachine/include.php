<?php

/**
 * Broadcast Machine include file
 *
 * this file includes all sorts of useful functions.  It's called from just about every page,
 * so it also handles several global tasks, such as turning off magic quotes, setting some global
 * variables, checking to make sure we are configured properly, etc.
 * @package Broadcast Machine
 */

//error_reporting(E_ALL);
//ini_set('errors.display_errors', true);

// you could also put this in a .htaccess file
// php_flag session.use_trans_sid off
ini_set('session.use_trans_sid', false);

/*
	You can't turn off session.use_trans_sid on an individual script basis until PHP5,
	but this will accomplish the same thing
*/
ini_set('url_rewriter.tags', '');


// make sure that magic quotes are turned off
set_magic_quotes_runtime(0);


//
// if magic quotes on then get rid of them
// see: http://us3.php.net/get_magic_quotes_gpc
//
if ( get_magic_quotes_gpc( ) ) {
	if ( ! function_exists('array_map_recursive') ) {
		 function array_map_recursive($function, $data) {
				 foreach ( $data as $i => $item ) {
						 $data[$i] = is_array($item)
								 ? array_map_recursive($function, $item)
								 : $function($item) ;
				 }
				 return $data ;
		 }
	}

	$_GET = array_map_recursive('stripslashes', $_GET);
	$_POST = array_map_recursive('stripslashes', $_POST);
	$_COOKIE = array_map_recursive('stripslashes', $_COOKIE) ;
	$_REQUEST = array_map_recursive('stripslashes', $_REQUEST);

}



//
// start session up
//
session_cache_limiter('none');
session_start();

//
// globally set the permissions level, so someone can be more or less 
// restrictive if they want
// 
global $perm_level;
$perm_level = 0777;

global $do_mime_check;
$do_mime_check = true;

//
// set global vars for our cookie names, so that if they conflict with 
// some other software's config, they can be changed
//
global $usercookie;
global $hashcookie;
$usercookie = "bm_username";
$hashcookie = "bm_userhash";

//
// these will be the paths where we store files, etc, etc
//
global $data_dir;
global $thumbs_dir;
global $torrents_dir;
global $publish_dir;
global $rss_dir;
global $text_dir;
global $themes_dir;

if ( ! isset($data_dir) ) {
  $data_dir = "data";
  $thumbs_dir = "thumbnails";
  $torrents_dir = "torrents";
  $publish_dir = "publish";
  $rss_dir = "publish";
  $text_dir = "text";
  $themes_dir = "themes";
}


//
// include files for legacy code, data storeage and file sharing
//
require_once("legacylib.php");
require_once("datastore.php");
require_once("seeder.php");

global $store;

/*
	there's a couple functions in here that we might want to use
	without actually setting up BM, so we can use this flag to skip
	setup
*/
global $skip_setup;
if ( !( isset($skip_setup) && $skip_setup == 1 ) ) {

  if ( ! setup_data_directories() ) {

		include_once "theme_defaults.php";

    bm_header();
    $store->setupHelpMessage();
    bm_footer();
    exit;
  }
		
	if ( ! setup_helper_apps() ) {

		include_once "theme_defaults.php";

    bm_header();
    $store->setupHelperMessage();
    bm_footer();
		exit;
	}	
}

// send all content as utf-8
header("Content-type: text/html; charset=UTF-8");

// if we don't have a user yet, then send off to the newuser page

// this global will be set in newuser.php so that we don't get into a recursive loop here
global $NEW_USER;

if ( (!isset($NEW_USER) || $NEW_USER != 1) && isset($store) && count($store->getAllUsers()) <= 0 ) {
	logout();
	header('Location: ' . get_base_url() . 'newuser.php');
	exit;
}

if ( !( isset($skip_setup) && $skip_setup == 1 ) &&
	isset($_COOKIE[$usercookie]) && !isset($_SESSION["user"]) ) {

	global $store;
	global $usercookie;
	global $hashcookie;

	$username = $_COOKIE[$usercookie];
	$users = $store->getAllUsers();

	if ( isset($users[$username]) && $users[$username]['Hash'] == $_COOKIE[$hashcookie] ) {
		$users[$username]['Username'] = $username;
		$_SESSION['user'] = $users[$username];
	} 
}

//
// if the user has logged in through http auth, but doesn't have cookies on, or
// something like that, then this will grab their login info and put it in the
// session array
//
global $can_use_cookies;
$can_use_cookies = true;


//
// initialize our theme
//
global $settings;
if ( isset($settings['theme']) ) {
	global $themes_dir;
	$theme = $settings['theme'];
	$theme_path = $themes_dir . "/" . $theme . "/theme.php";

	if ( file_exists($theme_path) ) {
		require_once $theme_path;
	}
}

// theme_defaults.php and render.php will cover anything thats not in our custom theme file
require_once("theme_defaults.php");
require_once("render.php");

function active_theme() {
	global $settings;
	if ( isset($settings['theme']) ) {
		return $settings['theme'];
	}
	
	return NULL;
}

function theme_path() {
	global $settings;
	global $themes_dir;

	return $themes_dir . "/" . $settings['theme'];
}

/**
 * return the version number of this install
 * @returns install version number
 */
function version_number() {
	return 21;
}

/**
 * return a string with the version of this installation
 * @returns string string with the version of this installation
 */
function get_version() {
  return 'Release ' . version_number();
}

/**
 * figure out the base url of this installation and update it in our settings.  we shouldn't be storing
 * the base url as an absolute anywhere - doing this makes the app extremely unportable
 */
function update_base_url() {
  global $settings;
	$tmpurl = "http://" . $_SERVER['HTTP_HOST'] . dirname($_SERVER['PHP_SELF']) . "/";

  if ( isset($settings) && 
       ( $settings['base_url'] == '' || $settings['base_url'] != $tmpurl ) ) {
		$settings['base_url'] = $tmpurl;
		global $store;
		$store->saveSettings($settings);
  }

}

/**
 * Returns the base url of this tracker
 *
 * @returns the base url of this tracker - we could probably be a lot smarter about this
 */
function get_base_url() {

  global $settings;

	if ( isset($settings) && $settings['base_url'] != '' ) {
		return $settings['base_url'];
	}

  if ( isset($_SERVER['HTTP_HOST']) ) {
  	$url = "http://" . $_SERVER['HTTP_HOST'] . dirname($_SERVER['PHP_SELF']);
  } 
  else {
  	$url = "/" . dirname($_SERVER['PHP_SELF']);
  }

  // make sure the url doesnt have multiple slashes on the end (bug # 1211743)
  while ( $url{strlen($url)-1} == '/' ) {
    $url = substr($url, 0, strlen($url) - 1);
  }
  
  // make sure the url ends with a slash
  if ( $url{strlen($url)-1} != '/' ) {
    $url .= "/";
  }
  
  return $url;
}



/**
 * Decodes a bEncoded string into a PHP structure
 *
 * @see http://www.monduna.com/bt/faq.html#TERM_13
 * @returns array of data
 */
function bdecode($info) {
	$pos = 0;
	return bdecode_next( $info, $pos );
}

/**
 * Decodes a bEncoded string, setting $pos to the the next token
 *
 * @see http://www.monduna.com/bt/faq.html#TERM_13
 * @returns array of data
 */
function bdecode_next($info,& $pos) {
	
  $origpos = $pos;
  
  switch (substr($info,$pos,1)) {
  case 'i':
    $pos = strpos($info,'e',$pos)+1;
    return substr($info,$origpos+1,$pos-$origpos-2);
  case 'd':
    $ret = array();
    $pos++;
    
    while (substr($info,$pos,1) != 'e') {
      $key = bdecode_next($info,$pos);
      $istart = $pos;
      $val = bdecode_next($info,$pos);
      $ilen = $pos - $istart;
      $ret[$key] = $val;
      
      if ($key == "info") {
		$ret["sha1"] = sha1(substr($info, $istart, $ilen));
      }
    }
    
    $pos++;
    return $ret;
    
  case 'l':
    $ret = array();
    $pos++;
    
    while (substr($info,$pos,1) != 'e') {
      $ret[] = bdecode_next($info,$pos);
    }
    
    $pos++;
    return $ret;
    
  default:
    
    if (preg_match('/^(\d+):.*$/s',substr($info,$pos))) {
      $len = preg_replace('/^(\d+):.*$/s','\\1',substr($info,$pos));
      $pos += $len + 1 + strlen($len);
      return substr($info,$origpos+strlen($len)+1,$pos-$origpos-strlen($len)-1);
    } 
    else {
      return null; //There has been an error!
    }
    
  } // switch
  
}

/**
 * bEncodes a PHP structure
 *
 * turns a php array into a bencoded string so we can write it to disk
 * @returns string
 */
function bencode($struct) {

   if (is_array($struct)) {
     $out = 'd';
     ksort($struct);
     
     foreach($struct as $key => $value) {
       $out .= bencode($key);
       $out .= bencode($value);
     }
     
     $out .= 'e';
     return $out;
   } 
   else if (preg_match('/^(\+|\-)?\d+$/',$struct)) {
     return 'i'.$struct.'e';
   } 
   else {
     return strlen($struct).':'.$struct;
   }
}


/**
 * Returns the name of the current user
 *
 * @returns name of the current user
 */
function get_username() {

  if (isset($_SESSION['user'])) {
    return $_SESSION['user']['Username'];
  }
  else {
    return "";
  }
}


/**
 * return a hash of the user's password
 *
 * @returns password hash, or a blank string if no one is logged in
 */
function get_passhash() {
  if (isset($_SESSION['user'])) {
    return $_SESSION['user']['Hash'];
  }
  else {
    return "";
  }
}



/**
 * generate a hash of the given username and password
 *
 * @returns generated hash
 */
function hashpass($username,$password) {
  return(sha1($username.$password."downhillb==31337"));
}

/**
 * log the user in
 *
 * @returns true and sets $_SESSION['user'] on success, false on error
 */
function login($username,$password,&$error, $set_cookies = true) {
	global $store;

	if ( ! $username || ! $password ) {
		return false;
	}

	$users = $store->getAllUsers();
	$username = trim(mb_strtolower($username));

	if (!isset($users[$username])) {
		$error = "User &quot;" . $username . "&quot; does not exist.";
		return false;
	} 
	else if ($users[$username]['Hash'] != hashpass($username, $password) ) {
		$error = "Incorrect password.";
		return false;
	} 

	$users[$username]['Username'] = $username;
	$_SESSION['user'] = $users[$username];
	
	
	if ( $set_cookies == true ) {
		global $usercookie;
		global $hashcookie;

		setcookie($usercookie, $username, 0, dirname($_SERVER['PHP_SELF']) );
		setcookie($hashcookie, hashpass($username, $password), 0, dirname($_SERVER['PHP_SELF']) );
	}
	return true;
}


/**
 * logout the user
 *
 * @returns true always
 */
 function logout() {

	global $usercookie;
	global $hashcookie;
	
	$expire = time()-42000;

	setcookie($usercookie, "", $expire, dirname($_SERVER['PHP_SELF']) );
	setcookie($hashcookie, "", $expire, dirname($_SERVER['PHP_SELF']) );

  unset($_SESSION['user']);

	// Unset all of the session variables.
	$_SESSION = array();
	
	// If it's desired to kill the session, also delete the session cookie.
	// Note: This will destroy the session, and not just the session data!
	if (isset($_COOKIE[session_name()])) {
		 setcookie(session_name(), '', $expire, dirname($_SERVER['PHP_SELF']));
	}
	
	// Finally, destroy the session.
	@session_destroy();	
	return true;
}

/**
 * do an HTTP AUTH login
 *
 * we do http auth when the user isn't already logged in and hits a download that requires
 * authorization - this works in browsers and programs such as DTV which don't use cookies
 * @returns true if logged in, exists processing otherwise (if user hits cancel in login process)
 */
function do_http_auth() {

	if ( ! isset($_SESSION['user']) ) {
		
		// check if the current loading of the page is the first loading
		// after a logout:
		if ( isset($_SESSION['logout']) ) {
		   unset($_SESSION['logout']);
		}
		
		if (! isset($_SESSION['realm'])) {
		   $_SESSION['realm'] = site_title();
		}
		
		// check if a user has already logged in before:
		if (isset($_SESSION['user'])) {
		   unset($_SESSION['login']);
		   return true;
		}
		

		//
		// check if a user just entered a username and password:
		//
	   if ( isset($_SERVER['PHP_AUTH_USER']) && $_SERVER['PHP_AUTH_USER'] &&
			login($_SERVER['PHP_AUTH_USER'], $_SERVER['PHP_AUTH_PW'], $errstr) ) {
		   unset($_SESSION['login']);
		   return true;
		}
		
		/** 
		 * if this PHP is running as a CGI, http auth won't work without this hack
		 * (see http://us3.php.net/manual/en/features.http-auth.php#52405)
		 *
		 * and also this mod_rewrite in our .htaccess file
				<IfModule mod_rewrite.c>
					 RewriteEngine on
					 RewriteRule .* - [E=REMOTE_USER:%{HTTP:Authorization},L]
				</IfModule>
			*/
		else if ( isset($_SERVER["REMOTE_USER"]) || isset($_SERVER["REDIRECT_REMOTE_USER"]) ) {
			$str = isset($_SERVER["REMOTE_USER"]) ? $_SERVER["REMOTE_USER"] : $_SERVER["REDIRECT_REMOTE_USER"];

			if ( beginsWith($str, "Basics") ) {
				$match = '/Basics +(.*)$/i';
			}
			else {
				$match = '/Basic +(.*)$/i';
			}
			preg_match($match, $str, $matches);
	
			$a = base64_decode( substr($str, 6) ) ;
			if ( strlen($a) > 0 && strcasecmp($a, ":" ) != 0 ) {
				list($name, $password) = explode(':', base64_decode($matches[1]));
				$_SERVER['PHP_AUTH_USER'] = strip_tags($name);
				$_SERVER['PHP_AUTH_PW']    = strip_tags($password);

				if ( login($_SERVER['PHP_AUTH_USER'], $_SERVER['PHP_AUTH_PW'], $errstr) ) {
					 unset($_SESSION['login']);
					 return true;
				}

			}		
		}
		
		// let the browser ask for a username and a password:
		$_SESSION['login'] = true;
		header("WWW-Authenticate: Basic realm=\"{$_SESSION['realm']}\"");
		header("HTTP/1.0 401 Unauthorized");
		echo "You need to log in before you can access this page.";
//		return false;
		exit;
	}
	else {
		return true;
	}
}


/**
 * make sure that we have a valid user
 *
 * make sure that the user's session information hasn't been somehow spoofed,
 * that they haven't been deleted, the password changed, etc, etc.
 * @returns true if valid, false otherwise
 */
function valid_user() {

  global $store;
//  $users = $store->getAllUsers();

  if ( !isset($_SESSION['user']) || 
				$_SESSION['user'] == "" || 
				!isset($_SESSION['user']) 
//				|| 
//				!isset($users[$_SESSION['user']['Username']])
				) {
    return false;
  }
	
  return true;
}

/**
 * return true if the user has admin privileges, false otherwise
 * @returns true if the user is admin, otherwise false
 */
function is_admin() {
  return (isset($_SESSION['user']) && $_SESSION['user'] && 
	  isset($_SESSION['user']['IsAdmin']) && $_SESSION['user']['IsAdmin'] && 
	  valid_user() );
}

/**
 * return true if the user has upload privileges, false otherwise
 * @returns true if the user is allowed to upload, false otherwise
 */
function can_upload() {
  global $settings;
	
	// this is an admin user OR
  return (is_admin() || 
	  (
			// the site has open channels AND
	   $settings['HasOpenChannels'] && 
	   (
		 	// this is a valid user OR
	    ( isset($_SESSION['user']) && ( !isset($_SESSION['user']['IsPending']) || $_SESSION['user']['IsPending'] == false ) ) || 

			// you don't need to be registered to post a file
			!$settings['UploadRegRequired'])
	   )
	  );
}


/**
 * return the title of the site, if it has been specified
 * @returns title of site, or a blank string if it hasn't been specified
 */
function site_title() {
  global $settings;
  return isset($settings['title']) ? $settings['title'] : 'Site Title';
}

/**
 * return the description of the site, if it has been specified
 * @returns description of site, or a blank string if it hasn't been specified
 */
function site_description() {
  global $settings;
  return isset($settings['description']) ? $settings['description'] : 'Site Description';
}

/**
 * return the site image/icon, if it has been specified
 * @returns site image/icon, if it has been specified, t.gif if not
 */
function site_image() {
  global $settings;
  return isset($settings['image']) ? $settings['image'] : 't.gif';
}



/**
 * setup our data directories
 *
 * process here: 1 - try and setup mysql, if that fails, we assume that we 
 * are using flat-file storage, so try and set that up.  if it fails, call 
 * setupHelpMessage to get the user to do whatever needs doing
 * to finalize our setup.  finally, once the data system is built, start the
 * seeder and call the setup function for that as well.
 * @returns true if everything worked, otherwise exits processing
 */
function setup_data_directories( $force = false ) {

//  debug_message("setup_data_directories");

  global $store;
  global $seeder;

  // if we've already setup our datastore, just return it
  // unless we want to force it to be re-created
  if ( $force == false && isset($store) && $store != null ) {
//    debug_message("returning pre-existing datastore");
    return $store;
  }

//  debug_message("create new datastore");
  $store = new DataStore();
	
	if ( !isset($store) || $store->is_setup == false ) {
 //   debug_message("setup_data_directories - failed");
		return false;
	}

 // debug_message("init datastore");
	$store->init();
 // debug_message("done with init");

  global $data_dir;
  if ( $store->type() == 'flat file' && ( !file_exists( $data_dir . '/channels') || count($store->getAllChannels()) <= 0  ) ) {
    $store->addNewChannel( "First Channel" );
  }

 // debug_message("start seeder");
  $seeder = new ServerSideSeeder();
 // debug_message("start seeder 1");
  $seeder->setup();
 // debug_message("start seeder done");

 // debug_message("setup_data_directories - worked");
  return true;
}

function setup_helper_apps() {
	global $store;
	return $store->setupHelpers();
}


/**
 * recursively change the permissions of the specified path to the specified mode
 *
 * recursive chmod which we can run when the include.php file is loaded,
 * so that we can make sure that all our files have the right permissions.
 * @deprecated when BM is out of beta, we'll probably toss this.
 * @returns true if it worked, false if it failed
 */
function recursive_chmod($path, $filemode) {

  if (!is_dir($path))
    return chmod($path, $filemode);

  $dh = opendir($path);
  while ($file = readdir($dh)) {
    if($file != '.' && $file != '..') {
      $fullpath = $path.'/'.$file;
      if(!is_dir($fullpath)) {
	if (!chmod($fullpath, $filemode))
	  return FALSE;
      } else {
	if (!recursive_chmod($fullpath, $filemode))
	  return FALSE;
      }
    }
  }
  
  closedir($dh);
  
  if(chmod($path, $filemode)) {
    return TRUE;
  }
  else {
    return FALSE;
  }
}

/**
 * check to see if all our required directories exist
 *
 * we can call this to make sure that the filesystem hasn't been mucked with, etc.  this
 * function calls recursive_chmod to try and fix permissions issues.  right now, if this is
 * a mySQL install of BM, this function doesn't do anything.
 * @returns error string if something went wrong, nothing if everything is fine
 */
function check_folders() {

  global $perm_level;
  global $store;
	
  if ( ! $store ) {
    return;
  }  

  clearstatcache();

  $error = array();
  $good_perms = true;
  
  // check all of our directories to make sure we can read/write with them
  if ( $store->type() == "flat file" ) {

    $old_error_level = error_reporting(0);
    
    if ( ! file_exists('text') && ! mkdir('text', $perm_level ) ) {
      $error[] = "text";
      $good_perms = false;
    }
    else {
      recursive_chmod("text", $perm_level);
    }

    if (!file_exists('publish') && !mkdir('publish', $perm_level) ) {
      $error[] = "publish";
      $good_perms = false;
    }
    else {
      recursive_chmod("publish", $perm_level);
    }
    
    if (!file_exists( 'thumbnails') && ! mkdir( 'thumbnails', $perm_level) ) {
      $error[] = "thumbnails";
      $good_perms = false;
    }
    else {
      recursive_chmod("thumbnails", $perm_level);
    }
    
    if (!file_exists('data') && !mkdir('data', $perm_level)) {
      $error[] = "data";
      $good_perms = false;
    }
    else {
      recursive_chmod("data", $perm_level);
    }
    
    if (!file_exists('torrents') && !mkdir('torrents', $perm_level)) {
      $error[] = "torrents";
      $good_perms = false;
    }
    else {
      recursive_chmod("torrents", $perm_level);
    }
		
    error_reporting($old_error_level);
  }
  else if ( $store->type() == "MySQL" ) {
    
  }
	
  if ( $good_perms == false ) {
    return $error;
  }

}

/**
 * do a web request to see if our data files are accessible, which is a bad security risk
 * but should only happen on non-Apache installs
 * @see http://www.securitytracker.com/alerts/2005/Jul/1014449.html
 * @returns true if the files are accessible, false if not
 */
function check_access() {

	global $data_dir;

	$base = get_base_url();
	$users_url = $base . "$data_dir/users";
//	$files_url = $base . "$data_dir/files";
//	$channels_url = $base . "$data_dir/channels";
	
	$headers = @get_headers($users_url, 1);

	if ( isset($headers) && isset($headers[0]) && stristr($headers[0], "200 OK") > 0 ) {
		return true;
	}

	return false;
	
}



/**
 * check to see if all our required directories have the right permission level
 *
 * we can call this to make sure that the filesystem hasn't been mucked with, etc.  this
 * function doesn't try and fix any problems.  if this is a mySQL install of BM, this function 
 * doesn't do anything.
 * @returns error string if something went wrong, nothing if everything is fine
 */
function check_permissions() {

  global $perm_level;
  global $store;
	
  if ( ! $store ) {
    return;
  }

  clearstatcache();

  $error = array();
  $good_perms = true;
  
  // check all of our directories to make sure we can read/write with them
  if ( $store->type() == "flat file" ) {

    $old_error_level = error_reporting(0);
    
    if ( ! is_writable('text') || ! is_readable('text') ) {
      $error[] = "text";
      $good_perms = false;
    }
    if ( ! is_writable('publish') || ! is_readable('publish') ) {
      $error[] = "publish";
      $good_perms = false;
    }
    if ( ! is_writable('thumbnails') || ! is_readable('thumbnails') ) {
      $error[] = "thumbnails";
      $good_perms = false;
    }
    if ( ! is_writable('data') || ! is_readable('data') ) {
      $error[] = "data";
      $good_perms = false;
    }
    if ( ! is_writable('torrents') || ! is_readable('torrents') ) {
      $error[] = "torrents";
      $good_perms = false;
    }
		
    error_reporting($old_error_level);

  }
  else if ( $store->type() == "MySQL" ) {
	
  }
	
  if ( $good_perms == false ) {
    return $error;
  }

}


/**
 * output our blogtorrent client detector script
 */
function draw_detect_scripts() {
?>

<script language="JavaScript" type="text/javascript" >
<!--

function hasBlogTorrent() {
<?php
  //Detects IE with the client installed
	if (substr_count($_SERVER['HTTP_ACCEPT'],'application/x-blogtorrent')>0) {
	  echo "return true;\n";
	} 
	else {
?>

		//Detects Mozilla browser with the client installed
		for (count=0;count<window.navigator.plugins.length;count++) {
			if (window.navigator.plugins[count].name.substring(0,12) == "Blog Torrent") {
				return true;
			}
		}
	
		// No client is installed
		return false;
<?php 
	} 
?>

}

function hasWindows() {
    return (navigator.userAgent.indexOf('Windows') > 0);
}

function hasMac() {
    return (navigator.userAgent.indexOf('Mac') > 0);
}
-->
</script>
<?php
}



/**
 * draw the HTML which will kickstart the blog torrent upload helper for the user
 */
function draw_upload_link() {

  $user = get_username();

  global $store;
  $hash = $store->getAuthHash($user, get_passhash());
  debug_message("draw_upload: AuthHash - $hash");
?>

<script language="JavaScript" type="text/javascript" >
<!--

parent.hash = "<?php echo $hash; ?>";

//
// check to see if the user has the helper installed -- if not we will send them
// a trigger link which will send along the helper with the trigger hash as well
//
if ( ! hasBlogTorrent() ) {

	if(confirm("You don't appear to have the Broadcast Machine Helper installed.  Click 'OK' to install the Broadcast Machine Helper now or 'Cancel' if you already have the Broadcast Machine Helper installed")) {

		// if this user is on a mac, send the mac helper
		if ( hasMac() ) {
			self.location.replace('trigger.php?type=mac&hash=<?php echo $hash; ?>');
		}
		// otherwise, send the PC helper - we should have logic here for non PC/Mac people
		else if ( hasWindows() ) {
			self.location.replace('trigger.php?type=exe&hash=<?php echo $hash; ?>');
		}
		else {
			alert("It looks like you aren't using a Mac or a Windows computer - the BM Helper doesn't work on other platforms");
		}

	} 
	else {
		self.location.replace('trigger.php?hash=<?php echo $hash; ?>');
	}
}

function sendUpload() {
  if (hasBlogTorrent()) {
    document.location.replace("trigger.php?hash=<?php echo $hash; ?>");
  }
}
-->
</script>

<?php
}

/**
 * take $int and convert it to a unit32
 *
 * from php.net - V == unsigned long (always 32 bit, little endian byte order)
 * @returns uint32
 */
function packint32($int) {
	return pack("V",$int);
}

/**
 * Sends an installer to the browser with file $tackon on the end
 *
 * Sends an installer to the browser with file $tackon on the end
 * if data is not null, sends data, only uses $tackon for the name
 * @returns nothing, echoed straight to client
 */
function send_installer( $tackon, $data = null ) {
	
	global $store;

	set_time_limit(0);

	$magicNumber = 560097380;
	$file = "nsisinstaller.exe";

	if (is_null($data)) {
		$torrent = $store->getRawTorrent($tackon);
	}
	else {
		$torrent = $data;
	}
	
	$len = strlen($torrent);
	$crc = crc32($torrent);
	$torrent .= packint32($crc).packint32($len).packint32($magicNumber);
	
	// output $file to the browser
//	readfile($file);

	$fd = fopen($file, "rb");
	header("Content-Type: application/force-download");
	header('Content-Disposition: attachment; filename="' . basename($tackon).".exe\"");
//  header("Content-type: application/octet-stream");
  header("Content-length:".(string)(filesize($file) + strlen($torrent) ));

	fpassthru($fd);
	fclose($fd);

	// echo the torrent as well
	echo $torrent;
}

/**
 * Sends a mac installer with file $tackon on the end
 *
 * if data is not null, sends data, only uses $tackon for the name
 * @returns nothing, echoes straight to browser
 */
function send_mac_installer( $tackon, $data=null ) {

  global $store;
	global $data_dir;
	
  header("Content-type: application/octet-stream");
  header("Content-disposition: attachment; filename=BlogTorrent.zip");
	
  if (file_exists('macclient.obj')) {
    $zip = unserialize( file_get_contents($data_dir . 'macclient.obj'));
  }
  else {
    $zip = unserialize( file_get_contents($data_dir . '/macclient.obj'));
  }
	
  if (is_null($data)) {
    $torrent = $store->getRawTorrent($tackon);
  }
  else {
    $torrent = $data;
  }
	
  $zip->add_file($torrent,'BM Helper.app/Contents/EasyDownload.torrent');
	
  echo $zip->file();
}


/**
 * Sends a mac uploader with file $tackon on the end
 *
 * if data is not null, sends data, only uses $tackon for the name
 * @returns nothing, echoes straight to browser
 */
function send_mac_uploader($tackon,$data=null) {

  global $store;
	global $data_dir;

  header("Content-type: application/octet-stream");
  header("Content-disposition: attachment; filename=BlogTorrent.zip");

  if (file_exists('macclient.obj')) {
    $zip = unserialize( file_get_contents('macclient.obj'));
  }
  else {
    $zip = unserialize( file_get_contents($data_dir . '/macclient.obj'));
  }

  if (is_null($data)) {
    $torrent = $store->getRawTorrent($tackon);
  }
  else {
    $torrent = $data;
  }

  $zip->add_file($torrent,'BM Helper.app/Contents/EasyUpload.blogtorrent');
  echo $zip->file();

}


/**
 * determine if we allow new users to register
 * @returns true if users can register, false otherwise
 */
function allowAddNewUser() {
	global $settings;
	return $settings['AllowRegistration'];
}

/**
 * this function can be called for sections of the website that require user access.
 * if they aren't logged in, they'll be sent to the login page.
 * NOTE - we could just show the login form, then reload the requested page, which makes a lot more sense
 */
function requireUserAccess($do_login = false) {

	$got_user = true;

	if ( ! isset($_SESSION['user']) || (
		isset($_SESSION['user']['IsPending']) && $_SESSION['user']['IsPending'] == true ) ) {

		$got_user = false;
	}
	else if ( !valid_user() ) {
		$got_user = false;
	}

	if ( ! $got_user ) {
		if ( $do_login == true ) {
			header('Location: ' . get_base_url() . 'login.php' );
		}
		else {
			header('Location: ' . get_base_url() . 'index.php' );
		}
		exit;
	}
}

/**
 * call from pages that require upload access to prevent unauthorized access
 */
 function requireUploadAccess() {

	if (!can_upload()) {
		header('Location: ' . get_base_url() . 'admin.php');
		exit;
	}

}

/**
 * simple comparison function for sorting arrays
 */
function comp($a, $b) {
	return ($b[1] - $a[1]);
}

/**
 * strip output of html and convert it to UTF-8
 * @returns formatted string
 */
function encode($s) {
  $s = preg_replace('!((?:[0-9\.]0|[1-9]|\d[\'"])\ ?)x(\ ?\d)!', '$1&#215;$2', $s);

  // this preg_replace is found on http://us2.php.net/manual/en/function.htmlspecialchars.php
  // and fixes the problem of htmlspecialchars replacing & with &amp and breaking character entities
  //	return preg_replace("/&amp;(#[0-9]+|[a-z]+);/i", "&$1;", strip_tags($s, "<b><strong><i><em><ul><li><ol>"));

  // strip non-ascii characters
  $s = trim($s,"\x7f..\xff\x0..\x1f");
  //print "$s<br>";

  $s = preg_replace(
		    "/&amp;(#[0-9]+|[a-z]+);/i", "&$1;", 
		    //		  htmlentities(
		    strip_tags(//$s,
			       //utf8_decode($s),
			       html_entity_decode($s),
			       "<b><strong><i><em><ul><li><ol>"
			       )
		    //			       )
		    );
  
  return $s;
}

/*function encode($s) {
  print "$s<br>";
  $s = preg_replace('!((?:[0-9\.]0|[1-9]|\d[\'"])\ ?)x(\ ?\d)!', '$1&#215;$2', $s);
  print $s . "<br>";

	// this preg_replace is found on http://us2.php.net/manual/en/function.htmlspecialchars.php
	// and fixes the problem of htmlspecialchars replacing & with &amp and breaking character entities
  //	return preg_replace("/&amp;(#[0-9]+|[a-z]+);/i", "&$1;", strip_tags($s, "<b><strong><i><em><ul><li><ol>"));

  // string non-ascii characters
  $s = trim($s,"\x7f..\xff\x0..\x1f");
  $s = preg_replace(
                    "/&amp;(#[0-9]+|[a-z]+);/i", "&$1;", 
                      htmlentities(
                                   strip_tags(
                                              utf8_decode($s),
                                              //html_entity_decode($s),
                                              "<b><strong><i><em><ul><li><ol>"
                                              )
                                   )
                      );
  
  print "$s<br>";
  return $s;

}
*/

/**
 * try and figure out the size of the given file
 * @returns filesize
 */
function get_filesize($tmpurl) {
	//
	// if this is a local file, then let's get the size info from the filesystem
	//
	if ( is_local_file($tmpurl) ) {

		// if it's a torrent, we'll figure out the size of it's component files
		if ( is_local_torrent($tmpurl) ) {

			$filename = local_filename($tmpurl);
			
			global $store;
			$tmp = $store->getTorrent( $filename );

			if ( isset($tmp["info"]["length"]) ) {
				$length = $tmp["info"]["length"];
			}
			else {
				$length = 0;
			}
		}
		// otherwise, return the size of the file
		else if ( file_exists("torrents/" . local_filename($tmpurl) ) ) {
			$length = filesize( "torrents/" . local_filename($tmpurl) );
		}
		else {
			$length = 0;
		}
	}
	else {
		$length = get_content_length($tmpurl, $errstr);
	}
	
	return $length;

}

/**
 * generate RSS for the given channel
 */
function makeChannelRss($channelID, $use_cache = true) {
	
	global $store;
	global $perm_level;
	global $rss_dir;
	
	if ( ! $channelID || $channelID == "" ) {
		return;
	}

	//
	// make sure we have our publish directories
	//
	if (!file_exists($rss_dir)) {
		mkdir($rss_dir, $perm_level);
		$use_cache = false;
	}
	else {

		$rss_publish_time = 0;
		if ( file_exists("$rss_dir/" . $channelID . ".rss") ) {
			$rss_publish_time = filemtime("$rss_dir/$channelID.rss");
		}
	
		// force an rss rebuild if we've updated our rss-generation code
		if ( filemtime("include.php") > $rss_publish_time ) {
			$use_cache = false;
		}
		else if (!file_exists("$rss_dir/" . $channelID . ".rss")) {
			$use_cache = false;
		}
		else {
	
			$last_publish_time = $store->getRSSPublishTime($channelID);
			
			if ( $last_publish_time == 0 || $last_publish_time >= $rss_publish_time ) {
				$use_cache = false;
			}	
		}
	} // else


	if ( $use_cache == true ) {
		return;
	}


	$base_url = get_base_url();
	$rss_files = array();


	$filename = $channelID . ".rss";
	if ( $channelID == "ALL" ) {
		$link = $base_url;
		$description = site_description();
		$name = site_title();
		$icon = site_image();
		
		$files = $store->getAllFiles();
		$channels = $store->getAllChannels();

		foreach($files as $filehash => $data) {
			if ($data["Publishdate"] <= time()) {
				foreach($channels as $c) {
					if ( $store->channelContainsFile($filehash, $c) ) {
						$data["channelID"] = $c["ID"];
						$rss_files[$filehash] = $data;
					}
				}
			} // if ( file published)
		}
	} // if all
	else {
		$channel = $store->getChannel($channelID);
		$link = $channel['LibraryURL'];
		if ( isset($channel['Icon']) ) {
			$icon = $channel['Icon'];
		}
		else {
			$icon = '';
		}

		if ( !isset($channel['Description']) ) {
			$channel['Description'] = '';
		} 
		$description = $channel['Description'];
		$name = $channel['Name'];
		
		// only go through this if we actually have files to display
		if ( is_array($channel["Files"]) ) {
			$channel_files = $channel["Files"];
			usort($channel_files, "comp");
		
			$files = $store->getAllFiles();
		
			foreach ($channel_files as $file) {
			
				if (array_key_exists($file[0], $files)) {
	
					$data = $files[$file[0]];
		
					if ($data["Publishdate"] <= time()) {
						$data["channelID"] = $channelID;
						$rss_files[$file[0]] = $data;
					} // if ( file published )

				} // if ( $file in channel )

			} // foreach

		} // if 

	} // else (channel)

  if ( $name == "" ) {
    $name = "Broadcast Machine";
  }

	outputRSSFile($filename, $channelID, $name, $description, $link, $icon, $rss_files );
}

function outputRSSFile($filename, $channelID, $name, $description, $link, $icon, $rss_files ) {

  global $store;

	$sOut = '<?xml version="1.0" encoding="utf-8"?>';

	$sOut .= <<<EOF
<rss version="2.0" 
	xmlns:media="http://search.yahoo.com/mrss" 
	xmlns:creativeCommons="http://backend.userland.com/creativeCommonsRssModule"
	xmlns:dtvmedia="http://participatoryculture.org/RSSModules/dtv/1.0">

EOF;

	$sOut .= "
	<channel><title>" . encode($name) . "</title>
			<description>" . encode($description) . "</description>
			<link>" . linkencode($link) . "</link>
			<dtvmedia:libraryLink>" . linkencode($link) . "</dtvmedia:libraryLink>
			<pubDate>" . date('r', time()) . "</pubDate>
			<generator>Broadcast Machine version " . version_number() . "</generator>
			<atom:link 
				 rel=\"self\" 
				 type=\"application/rss+xml\" 
				 title=\"" . encode($name) . "\" 
				 href=\"" . get_base_url() . "rss.php?i=$channelID\" 
				 xmlns:atom=\"http://www.w3.org/2005/Atom\" />
				 ";

	foreach ($rss_files as $filehash => $data) {
		$detail_link = detail_link($data["channelID"], $filehash);
		$sOut .= '<item><title>' . encode($data['Title']) . '</title>
				<link>' . $detail_link . '</link>
				<guid isPermaLink="false">' . $filehash . '</guid>';
				
		if ( isset($data["donation_id"]) && $data["donation_id"] != "" ) {
			$sOut .= "\n";
			$donations = $store->getAllDonations();

			if ( isset(	$donations[$data["donation_id"]]["text"]) ) {
				$donate_text = $donations[$data["donation_id"]]["text"];
				$sOut .= "<dtvmedia:paymentLink><![CDATA[" . $donate_text . "]]></dtvmedia:paymentLink>\n";
			
			}					
		}

		// dont send a description flag if we don't have the data
		if ( $data["Description"] ) {
			$sOut .= '<description>' . encode($data['Description']) . "</description>\n";
		}

		$tmpurl = $data["URL"];
		$length = get_filesize($tmpurl);
		// ensure we have a positive length, which we need to produce valid rss
		if ( $length <= 0 ) {
			$length = 1;
		}


		$download_url = download_link($data["channelID"], $filehash );			
		$sOut .= "<enclosure url=\"$download_url\" ";

		// sometimes the mime-type comes with some extra data (like the charset)
		// make sure we remove that here
		if ( $data["Mimetype"] ) { 

			// if we have a junky mimetype, just set it to application/octet-stream - this
			// should help ensure that the file is downloaded as text by mistake
			if ( beginsWith($data["Mimetype"], "text") ) {
				$data["Mimetype"] = "application/octet-stream";
			}

			$junk = split(";", $data["Mimetype"]);
			$sOut .= 'type="' . $junk[0] . '" ';
		}
		// ensure we have a mime-type here.  this might not be ideal,
		// but we need this to produce valid rss
		else {
			$sOut .= 'type="application/octet-stream" ';
		}
				
		$sOut .= ' length="' . $length . '" ';
		
		$sOut .= '/>
				<pubDate>' . date("D, d M Y H:i:s O", $data["Publishdate"]) . "</pubDate>\n";

	
		// dont send if we dont have a thumbnail
		if ( $data["Image"] ) {
			$tmp = linkencode($data["Image"]);
			$tmp = str_replace("&", "&amp;", $tmp);
			$tmp = str_replace("&&amp;", "&amp;", $tmp);
			$sOut .= '<media:thumbnail url="' . $tmp . "\" />\n";
		}

		foreach ($data["People"] as $people) {
			if ( isset($people[0]) && isset($people[1]) ) {
        $name = $people[0];
        $role = $people[1];
/*				$role = str_replace("&", "&amp;", $people[1]);
				$role = str_replace("&&amp;", "&amp;", $role);
				$name = str_replace("&", "&amp;", $people[0]);
				$name = str_replace("&&amp;", "&amp;", $name);*/
				$sOut .= "<media:credit role=\"" . encode(mb_strtolower(trim($role))) . "\" scheme=\"urn:pculture-org:custom\">" .	encode(trim($name)) . "</media:credit>\n";
			}
		}

		$sOut .= "</item>\n";
	
	} // foreach

	// if we have a thumbnail, go ahead and display it
	if ( isset($icon) && $icon != "" ) {
		$sOut .= "
<image>
<title>" . encode($name) . "</title>
<url>" . linkencode($icon) . "</url>
<link>" . linkencode($link) . "</link>
</image>";
	}

	$sOut .= '</channel>';
	$sOut .= '</rss>';

	global $rss_dir;
	$handle = fopen($rss_dir . "/" . $filename, "a+b");
	flock($handle,LOCK_EX);
	fseek($handle,0);
	ftruncate($handle,0);
	fwrite($handle,$sOut);
	fclose($handle);
}

/**
 * code to handle returning a 304 if our RSS hasn't changed
 * @see http://simon.incutio.com/archive/2003/04/23/conditionalGet 
 */
function doConditionalGet($timestamp) {
    // A PHP implementation of conditional get, see 
    //   http://fishbowl.pastiche.org/archives/001132.html

//    $last_modified = substr(date('r', $timestamp), 0, -5).'GMT';
		$last_modified = $timestamp;
    $etag = '"'.md5($last_modified).'"';

    // Send the headers
    header("Last-Modified: $last_modified");
    header("ETag: $etag");

    // See if the client has provided the required headers
    $if_modified_since = isset($_SERVER['HTTP_IF_MODIFIED_SINCE']) ?
        $_SERVER['HTTP_IF_MODIFIED_SINCE'] :
        false;
    $if_none_match = isset($_SERVER['HTTP_IF_NONE_MATCH']) ?
        $_SERVER['HTTP_IF_NONE_MATCH'] : 
        false;

    if (!$if_modified_since && !$if_none_match) {
        return;
    }
    // At least one of the headers is there - check them
    if ($if_none_match && $if_none_match != $etag) {
        return; // etag is there but doesn't match
    }
    if ($if_modified_since && $if_modified_since != $last_modified) {
        return; // if-modified-since is there but doesn't match
    }
    // Nothing has changed since their last request - serve a 304 and exit
    header('HTTP/1.0 304 Not Modified');
    exit;
}

/**
 * display the RSS for the specified channel
 */
function displayChannelRSS($channelID) {

	global $rss_dir;
	$rss_file = "$rss_dir/" . $channelID . ".rss";

//	if ( !file_exists($rssfile) || filemtime("include.php") > filemtime($rssfile) ) {
	if ( !file_exists($rss_file) ) {
		makeChannelRss($channelID);
	}

	$filedate = gmdate("D, d M Y H:i:s", filemtime($rss_file)) . " GMT";
//	$last_modified = substr(date('r', $filedate), 0, -5).'GMT';
 
 	// see if the file has been modified or not.  if not, this function
 	// will return a 304 code and exit processing
 	doConditionalGet($filedate);

	// otherwise, return the file
	print( file_get_contents($rss_file));
}

/**
 * check $str to see if it begins with $sub
 * @returns true/false
 */
function beginsWith( $str, $sub ) {
	$str = mb_strtolower($str);
	$sub = mb_strtolower($sub);
  return ( substr( $str, 0, strlen( $sub ) ) == $sub );
}

/**
 * check $str to see if it ends with $sub
 * @returns true/false
 */
function endsWith( $str, $sub ) {
	$str = mb_strtolower($str);
	$sub = mb_strtolower($sub);
   return ( substr( $str, strlen( $str ) - strlen( $sub ) ) == $sub );
}


/**
 * try and figure out the length of the specified URL
 * @returns length, and sets $errstr if something goes wrong - like a 404
 */
function get_content_length( $file_url, &$errstr ) {
	$headers = @get_headers($file_url, 1);

	if ( ! $headers || stristr($headers[0], "404") != 0 ) {
		$errstr = "404";
		return 0;
	}

	if ( isset($headers["content-length"]) ) {
		return $headers["content-length"];
	}
	else {
		return 0;
	}
}


/** 
 * encode a URL so that browsers can handle it properly
 * @see http://us4.php.net/manual/en/function.rawurlencode.php comments
 * @returns url
 */
function linkencode($p_url){
   $uparts = @parse_url($p_url);

   $scheme = array_key_exists('scheme',$uparts) ? $uparts['scheme'] : "";
   $pass = array_key_exists('pass',$uparts) ? $uparts['pass']  : "";
   $user = array_key_exists('user',$uparts) ? $uparts['user']  : "";
   $port = array_key_exists('port',$uparts) ? $uparts['port']  : "";
   $host = array_key_exists('host',$uparts) ? $uparts['host']  : "";
   $path = array_key_exists('path',$uparts) ? $uparts['path']  : "";
   $query = array_key_exists('query',$uparts) ? $uparts['query']  : "";
   $fragment = array_key_exists('fragment',$uparts) ? $uparts['fragment']  : "";

   if(!empty($scheme))
     $scheme .= '://';

   if(!empty($pass) && !empty($user)) {
     $user = rawurlencode($user).':';
     $pass = rawurlencode($pass).'@';
   } else if(!empty($user))
     $user .= '@';

   if(!empty($port) && !empty($host))
       $host = ''.$host.':';
   else if(!empty($host))
       $host=$host;

   if(!empty($path)){
     $arr = preg_split("/([\/;=])/", $path, -1, PREG_SPLIT_DELIM_CAPTURE); // needs php > 4.0.5.
     $path = "";
     foreach($arr as $var){
       switch($var){
       case "/":
       case ";":
       case "=":
         $path .= $var;
         break;
       default:
         $path .= rawurlencode($var);
       }
     }
     // legacy patch for servers that need a literal /~username
     $path = str_replace("/%7E","/~",$path);
   }

   if(!empty($query)){
     $arr = preg_split("/([&=])/", $query, -1, PREG_SPLIT_DELIM_CAPTURE); // needs php > 4.0.5.
     $query = "?";
     foreach($arr as $var){
       if( "&" == $var || "=" == $var )
         $query .= $var;
       else
         $query .= urlencode($var);
     }   
   }

   if(!empty($fragment))
     $fragment = '#'.urlencode($fragment);

   return implode('', array($scheme, $user, $pass, $host, $port, $path, $query, $fragment));
}




/**
 * determine if this is a local file or an external URL we are dealing with
 * @returns true/false
 */
function is_local_file($url) {

	// figure out what server we are one - since URLs sometimes have www
	// and sometimes don't, make sure we don't include that in the search
	global $torrents_dir;
	if ( file_exists( $torrents_dir . "/" . basename($url) ) ) {
		return true;
	}

	return false;
}
/*
function local_file_path($url) {
	$fname = basename($url);
	
}*/

/**
 * figure out if this is a .torrent file located within the control of BM.  
 * if so, we can share it
 * @returns true/false
 */
function is_local_torrent($url) {

	if ( is_local_file($url) 	&& endsWith( $url, ".torrent" ) ) {
		return true;
	}
	
	return false;
}


/**
 * figure out the name of a local file, given it's URL - basically, the URL stripped
 * of host information.
 * @returns local filename
 */
function local_filename($url) {

	if ( is_local_file($url) ) {
		return basename($url);
	}
	else {
		return false;
	}

}

/**
 * wrapper for deleting a file - we'll do some error checking, etc,
 * and try to suppress the worst of it.
 *
 * if there was an error and this is a server with a POSIX library, we'll
 * also set the global $errstr variable with a string describing the error.
 * @returns true if deleted, false if not
 */
function unlink_file($file) {
	if ( !file_exists($file) ) {
		return true;
	}
	
	$result = @unlink($file);

	// if we've got POSIX error functions, figure out what 
	// the error was - we might display it in a nice fashion	
	if ( $result == false && function_exists("posix_strerror") && function_exists("posix_get_last_error") ) {
		global $errstr;
		$errstr = posix_strerror( posix_get_last_error() );
	}
	
	return $result;

}

function html_encode_utf8($s) {
	$len = strlen($s);
	$x = 0;
	$result = "";
	while ($x<$len) {
		if (ord($s[$x])<128) {	
			$result .= $s[$x];
		} else if (ord($s[$x]) < 224) {
			$result .= "&#" . bindec(substr(decbin(ord($s[$x])),3) . substr(decbin(ord($s[$x+1])),2)) . ";";
			$x = $x + 1;
		} else if (ord($s[$x] < 239)) {
			$result .= "&#" . bindec(substr(decbin(ord($s[$x])),4) . substr(decbin(ord($s[$x+1])),2) . substr(decbin(ord($s[$x+2])), 2)) . ";";
			$x = $x + 2;
		}
		$x++;
	}
	return $result;
}

/**
 * check to see if the given pid is running
 * @returns true/false
 */
function is_process_running($p) {
	$p = trim($p);
	$pid = @exec("ps -p $p");
	$result = strpos($pid, $p);
	return stristr($pid, $p) ? true : false;
}

/**
 * try to figure out the extension of this file
 */
function get_extension_from_url($tmpurl) {

	if ( is_local_torrent($tmpurl) ) {
		return "torrent";					
	}
	else {

		$elements = @parse_url($tmpurl);
		if ( isset($elements["path"]) ) {
			$filename = basename($elements["path"]);
			$parts = explode(".", $filename);
		
			if ( is_array($parts) && count($parts) > 0 ) {
				require_once("mime.php");
		
				$ext = $parts[count($parts) - 1];
		
				if ( $ext != "" ) {
						return $ext;
				}
			} // if ( parts > 0 )
		} // if elements["path"]
	}

	return "";
}

function download_link($channel_id, $hash, $force_no_rewrite = false) {
	global $settings;
	global $store;

	$file = $store->getFile($hash);
	$ext = get_extension_from_url($file["URL"]);

	if ( $ext != "" ) {
		$ext = ".$ext";
	}

	if ( $force_no_rewrite == false && isset($settings['use_mod_rewrite']) && $settings['use_mod_rewrite'] == true ) {
		$url = get_base_url() . "download/$channel_id/$hash$ext";
	}
	else {
		$url = get_base_url() . "download.php?c=" . $channel_id . "&amp;i=" . $hash . "&amp;e=$ext";
	}
	
	//debug_message($url);
	return $url;
}


function detail_link($channel_id, $hash, $force_no_rewrite = false) {
	global $settings;

	if ( $force_no_rewrite == false &&  isset($settings['use_mod_rewrite']) && $settings['use_mod_rewrite'] == true ) {
		$url = get_base_url() . "detail/$channel_id/" . $hash;
	}
	else {
		$url = get_base_url() . "detail.php?c=" . $channel_id . "&amp;i=" . $hash;
	}
	
	return $url;
}

function channel_link($channel_id, $force_no_rewrite = false) {
	global $settings;

	if ( $force_no_rewrite == false && isset($settings['use_mod_rewrite']) && $settings['use_mod_rewrite'] == true ) {
		$url = get_base_url() . "library/$channel_id";
	}
	else {
		$url = get_base_url() . "library.php?i=" . $channel_id;
	}
	
	return $url;
}

function rss_link($channel_id = "ALL", $for_itunes = false) {
	global $settings;
	if ( isset($settings['use_mod_rewrite']) && $settings['use_mod_rewrite'] == true ) {
		$url = get_base_url() . "rss/$channel_id";
		if ( $for_itunes == true ) {
		   $uparts = @parse_url($p_url);
		   $scheme = array_key_exists('scheme', $uparts) ? $uparts['scheme'] : "http";
       $url = str_replace($scheme, "itpc", $url);
		}
	}
	else {
		$url = get_base_url() . "rss.php?i=" . $channel_id;
	}
	
	return $url;
}

function write_mod_rewrite($on = true) {

	$base = preg_replace( '|^(.*[\\/]).*$|', '\\1', $_SERVER['PHP_SELF'] );

	$rules = <<<EOF
###
### MOD REWRITE RULES (DO NOT EDIT)
###
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase $base
RewriteRule ^rss/([0-9]+) rss.php?i=$1 [QSA]
RewriteRule ^library/([0-9]+) library.php?i=$1 [QSA]
RewriteRule ^detail/([0-9]+)/(.*)$ detail.php?c=$1&i=$2 [QSA]
RewriteRule ^download/([0-9]+)/(.*)$ download.php?c=$1&i=$2&type=direct [QSA]		
</IfModule>
EOF;


  $old_error_level = error_reporting(0);
	$f = fopen(".htaccess", 'wb');
  error_reporting($old_error_level);

  if ( ! $f || !is_resource($f) ) {
    return false;
  }

	flock( $f, LOCK_EX );
	rewind ( $f );

	$file = "";
	while ( !feof( $f ) ) {
		$file .= fread( $f, 8192 );
	}

	if ( $on == true ) {
		if ( stristr( $file, "### MOD REWRITE RULES (DO NOT EDIT)" ) === false ) {
			$file .= $rules;	
			ftruncate($f, 0);
			fwrite($f, $file);
		}
	}
	else {
		if ( stristr( $file, "### MOD REWRITE RULES (DO NOT EDIT)" ) !== false ) {
			str_replace( $rules, "", $file );	
			ftruncate($f, 0);
			fwrite($f, $file);
		}
	}

	flock( $f, LOCK_UN );
	fclose($f);
  return true;
}

function debug_message($str) {
//  error_log($str);
}

function do_query($sql) {
//  debug_message($sql);
//  print("$sql<br>");
  return mysql_query($sql);
}

function list_themes() {
	global $themes_dir;
	$themes = dir($themes_dir);
	$choices = array();

  // load in a list of themes
	while(($themestr = $themes->read()) !== false) {	
		if ( $themestr != "." && $themestr != ".." && $themestr != ".svn") {
			$choices[$themestr]["id"] = $themestr;
			if ( file_exists($themes_dir . "/" . $themestr . "/description.txt") ) {
				$choices[$themestr]["description"] = file_get_contents($themes_dir . "/" . $themestr . "/description.txt");
			}
			if ( file_exists($themes_dir . "/" . $themestr . "/icon.gif") ) {
				$choices[$themestr]["icon"] = $themes_dir . "/" . $themestr . "/icon.gif";
			}
		}
	} // while

  return $choices;

}

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>