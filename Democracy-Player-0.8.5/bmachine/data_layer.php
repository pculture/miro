<?php
/**
 * data layer class defined here
 * @package BroadcastMachine
 */


/**
 * data layer for use in accessing a bencoded set of data files
 * @access public
 * @package BroadcastMachine
 */
class BEncodedDataLayer {

  /**
   * hang onto handles when a file is locked
   * @var array
   */
  var $_handles;

  /**
   * hooks that get called when data is loaded/saved/deleted.  this system
   * is pretty crude right now and could be fleshed out a lot.
   * @var array
   */
  var $_hooks;

  /**
   * default constructor
   */
  function BEncodedDataLayer() {
    $this->_handles = array();
    $this->_hooks = array();
  }

  /**
   * return the type of data layer
   * @returns type of data layer as a string
   */
  function type() {
    return "flat file";
  }
  
  /**
   * initialize the data layer.  returns true on success or false on failure.
   * this class is hardcoded to return true but other classes which inherit might
   * override this.
   * @returns true/false on success/failure
   */
  function init() {
    return true;
  }

  /**
   * setup BM - create directories, set permissions, write a couple of .htaccess files
   * @returns true if successful, false if not
   */
  function setup() {

    global $data_dir;
    global $torrents_dir;

    $old_error_level = error_reporting ( 0 );

    if ( make_folder($data_dir) == false ) {
      debug_message("$data_dir not writable, failing");
      return false;
    }
    if ( make_folder($torrents_dir) == false ) {
      debug_message("$torrents_dir not writable, failing");
      return false;
    }

    if ( !file_exists(  $data_dir . '/.htaccess' ) ) {
      debug_message("create .htaccess for data dir");
      write_deny_htaccess($data_dir);
    }

    if ( !file_exists( $torrents_dir . '/.htaccess' ) ) {
      write_deny_htaccess($torrents_dir);
    }

    error_reporting ( $old_error_level );

    return $this->loadSettings();
  }

  /**
   * take an incoming list of datafiles, either as an array or a comma-separated list,
   * and turn it into an array
   * @param array|string $list list of files to lock
   * @returns array of files to lock
   */
  function lockList($list) {
    if ( ! is_array($list) ) {
      $list = explode(",", $list);
    }
    foreach($list as $l) {
      $l = trim($l);
      $out[] = $l;
    }
    return $out;
  }

  /**
   * lock the specified files
   * @param array|string $list list of files to lock
   */
  function lockResources($list) {
    foreach($this->lockList($list) as $file) {
      $this->lockResource($file);
    }
  }

  /**
   * unlock the specified files
   * @param array|string $list list of files to unlock
   */
  function unlockResources($list) {
    foreach($this->lockList($list) as $file) {
      $this->unlockResource($file);
    }
  }

  /**
   * unlock anything that is currently locked
   */
  function unlockAll() {
    foreach( $this->_handles as $file => $h ) {
      $this->unlockResource($file);
      //clearstatcache();
    }
  }

  /**
   * lock the requested resource
   * @param string $file file to lock
   * @returns the handle if the file was locked, false if there was a problem
   */
  function lockResource($file) {
    if ( isset($this->_handles[$file]) ) {
      return $this->_handles[$file];
    }

    $old_error_level = error_reporting ( 0 );
    
    global $data_dir;
    $handle = fopen("$data_dir/$file", "a+b");		
    
    error_reporting ( $old_error_level );

    if ( isset($handle) && $handle != false ) {
      flock( $handle, LOCK_EX );
      $this->_handles[$file] = $handle;
      return $handle;
    }
    
    return false;
  }
  

  /**
   * unlock the specified file
   * @param string $file file to unlock
   */
  function unlockResource($file) {
    if ( isset($this->_handles[$file]) ) {
      $this->closeHandle($this->_handles[$file]);
      unset($this->_handles[$file]);
      //clearstatcache();
    }
  }

  /**
   * close out the specified handle, flushing any remaining data in the process
   * @param handle $h handle to close
   */
  function closeHandle($h) {
    fflush($h);
    flock($h, LOCK_UN );
    fclose($h);
  }
  
  /**
   * get a single item from the specified file
   * returns the item if it exists, null otherwise
   * @param string $file file to lock
   */
  function getOne($file, $id, $handle = null) {
    debug_message("getOne $file $id $handle");
    if ( $handle == null ) {
      $data = $this->getAll($file);
    }
    else {
      $data = $this->getAllLock($file, $handle, true);
    }

    if ( isset($data[$id]) ) {
      return $data[$id];
    }
    
    return null;	
  }

  /**
   * get all data from the specified file.  don't hold a lock
   * @param string $file file to load
   * @return array data from file
   */
  function getAll($file) {
    $handle = null;
    return $this->getAllLock($file, $handle, false);
  }
	
  /**
   * get all data from the specified file.  maintain a lock on the file if get_lock is true.
   *
   * @param string $file file to load
   * @param handle $handle handle for file.  if null, and $get_lock is true, this will be set on completion
   * @param boolean $get_lock hold the lock or not?
   * @return array of data
   */
  function getAllLock($file, &$handle, $get_lock = true ) {
    
    debug_message("flat getAllLock $file");
    global $data_dir;
    
    if ( $handle == null ) {
      debug_message("flat getAllLock: get handle for $file");
      $handle = $this->lockResource($file);
      debug_message($handle);
    }

    if ( $handle == false ) {
      global $errorstr;
      $errorstr = "Couldn't open $file";
      return false;
    }
    
    if ( $get_lock == true ) {
      $hold_lock = true;
      debug_message("hold lock on $file");
    }
    else {
      debug_message("Don't hold lock on $file");
      $hold_lock = false;
    }

    fseek( $handle, 0 );
    
    $contents = "";
    while ( !feof( $handle ) ) {
      $contents .= fread( $handle, 8192 );
    }
    
    if ( $hold_lock == false ) {
      debug_message("unlocking handle for $file");
      $this->unlockResource($file);
    }
    
    if ( $contents == "" ) {
      $contents = array();
    }
    else {
      $contents = bdecode( $contents );
    }
    
    $hooks = $this->getHooks($file, "get");
    if ( $hooks != null ) {
      foreach($contents as $key => $row) {
	$hooks($row);
      }
    }
    
    debug_message("loaded $file: " . count($contents) . " items");
    return $contents;
  }	
  
  /**
   * save a single item to the specified file, using $hash as the id
   * @param string $file file to save
   * @param array $data array of data for a single item
   * @pararm string $hash the ID of this item
   * @param handle $handle handle for file
   * @return true/false on success
   */
  function saveOne($file, $data, $hash, $handle = null) {
    
    if ( $handle == null ) {
      $handle = $this->lockResource($file);
      $hold_lock = false;
    }
    else {
      $hold_lock = true;
    }
    if ( !$handle ) {
      return false;
    }
    $all = $this->getAllLock($file, $handle);
    $all[$hash] = $data;
    
    $result = $this->saveAll($file, $all, $handle);	
    
    if ( $hold_lock == false ) {
      $this->unlockResource($file);
    }
    
    $hooks = $this->getHooks($file, "save");
    
    // call any 'save' hooks for this data type
    if ( $hooks != null ) {
      //      foreach ( $hooks as $h ) {
      $hooks( $all[$hash] );
      //      }
    }
    
    return $result;
  }
  
  /**
   * save the data to the specified file, using the handle if provided
   * @param string $file file to save
   * @param array $data array of all data elements to save
   * @param handle $handle handle for file
   * @return true/false on success
   */
  function saveAll($file, $data, $handle = null) {

    global $errorstr;
    
    debug_message("saveAll: $file $handle - " . count($data) . " items");
    if ( $handle == null ) {
      $handle = $this->lockResource($file);
      $hold_lock = false;
    }
    else {
      $hold_lock = true;
    }
    
    if ( ! $handle ) {
      $errorstr = "Couldn't open $file!";
      debug_message($errorstr);
      return false;
    }
    
    fseek($handle,0);
    ftruncate($handle,0);
    fseek($handle,0);
    fwrite($handle,bencode($data));

    // make sure the file is flushed out to the filesystem
    fflush($handle);

    if ( $hold_lock == false ) {
      $this->unlockResource($file);
    }
		
    // make sure we aren't holding onto a cached copy
    clearstatcache();

    $hooks = $this->getHooks($file, "save");

    // call any hooks
    if ( $hooks != null ) {
      foreach($data as $key => $row) {
	//				foreach ( $hooks as $h ) {
	$hooks($out[ $row[$key] ]);
	//				}
      }
    }
    
    return true;
  }

	
  /**
   * delete a single item from the file
   * @param string $file file
   * @param string $hash id of the item
   * @param handle $handle handle for file
   * @return true/false on success
   */
  function deleteOne($file, $hash, $handle = null) {
    debug_message("deleteOne $file $hash");	
    if ( $handle == null ) {
      $handle = $this->lockResource($file);
      $hold_lock = false;
    }
    else {
      $hold_lock = true;
    }
    
    if ( !$handle ) {
      return false;
    }
    debug_message("get pre-delete hooks");
    $hooks = $this->getHooks($file, "pre-delete");
    
    if ( $hooks != null ) {
      $hooks($hash, $handle);
    }
    
    debug_message("done calling pre-delete hooks");
    
    $all = $this->getAllLock($file, $handle, true);
    unset($all[$hash]);
    debug_message("done with unset");
    $result = $this->saveAll($file, $all, $handle);	
    debug_message("done with save");	
    $hooks = $this->getHooks($file, "post-delete");
    
    if ( $hooks != null ) {
      //			foreach ( $hooks as $h ) {
      $hooks($hash);
      //		}
    }
    
    if ( $hold_lock == false ) {
      $this->unlockResource($file);
    }
    
    return true;
  }
	

  /**
   * return any hooks for the specified datatype
   * @param string $file data type
   * @param string $when which type of hook we are looking for
   * @return string name of hook, or null if none exists
   */
  function getHooks($file, $when = "get") {
    if ( isset($this->_hooks[$file]) && isset($this->_hooks[$file][$when]) ) {
      return $this->_hooks[$file][$when];
    }
    return null;
  }
  

  /**
   * register a hook
   * @param string $file data type
   * @param string $when which type of hook this is
   * @param string name of hook
   */
  function registerHook($file, $when, $fn) {
    $this->_hooks[$file][$when] = $fn;
  }

  /**
   * check whether our settings exist or not
   * @returns true/false
   */
  function settingsExist() {
    global $data_dir;
    return file_exists(  $data_dir . '/settings' ) && filesize($data_dir . '/settings') > 0 ;
  }

  /**
   * load settings file
   * @returns true on success, false on failure
   */
  function loadSettings() {

    global $settings;

    $contents = '';

    if ( !$this->settingsExist() ) {
      $settings = array	(
                         'AllowRegistration'         => false,
                         'RequireRegApproval'    => false,
                         'RequireRegAuth'        => true,
                         'UploadRegRequired'     => true,
                         'DownloadRegRequired'   => false,
                         'DefaultChannel'        => '',
                         'HasOpenChannels'       => false,
                         'sharing_enable'        => false,
                         'sharing_auto'          => false,
                         'sharing_python'        => '',
                         'sharing_actual_python' => '',
			 'base_url'		 => ''
                         );
      
    }
    else {
      global $data_dir;
      $handle=fopen( $data_dir . '/settings', "rb" );
      flock( $handle, LOCK_EX );

      while ( !feof( $handle ) ) {
        $contents .= fread( $handle, 8192 );
      }
      
      $settings = bdecode( $contents );
      
      // early betas didn't have these settings
      if ( !isset( $settings['sharing_enable'] ) )
        $settings['sharing_enable']=false;
      
      if ( !isset( $settings['sharing_auto'] ) )
        $settings['sharing_auto']=true;
      
      if ( !isset( $settings['sharing_python'] ) )
        $settings['sharing_python']='';
      
      if ( !isset( $settings['sharing_actual_python'] ) )
        $settings['sharing_actual_python']='';

      if ( !isset( $settings['base_url'] ) )
        $settings['base_url']='';

      fflush ($handle);
      flock( $handle, LOCK_UN );
      fclose ( $handle );
      clearstatcache();
    }
    
    return true;
  }


  /**
   * Saves settings to config file
   * @returns true on success, false on failure
   */
  function saveSettings( $newsettings ) {

    global $settings;
    global $data_dir;

    $handle = fopen(  $data_dir . '/settings', "a+b" );
    flock( $handle, LOCK_EX );
    fseek( $handle, 0 );
    ftruncate( $handle, 0 );

    $settings  = $newsettings;
    fwrite( $handle, bencode( $settings ) );

    fflush ($handle);
    flock( $handle, LOCK_UN );
    fclose ( $handle );
    clearstatcache();

    return true;
  }

} // class BEncodedDataLayer
?>