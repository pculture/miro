<?php 
/**
 * server-seeding class
 *
 *  This file is part of BlogTorrent http://www.blogtorrent.com/
 *  nassar 'at' downhillbattle 'dot' org
 *  Licensed under the terms of the GNU GPL 
 *  
 *  
 *  We use a custom frontend for the official BitTorrent client to perform
 *  server-side seeding. It forks itself off as a background process and
 *  writes stats to a file automatically, so we don't need to depend on
 *  nohup or something similar being around.
 *  
 *  
 *  We chose to use a Python based BT client, so that platforms we don't
 *  explictly support can
 *  
 *  A stripped down Python interpreter for Linux x86 is included in the
 *  Broadcast Machine Helper distribution, so server sharing should work 
 *  automatically on most Linux servers. If you have a Mac OS X or UNIX 
 *  server, you'll need to tell Broadcast Machine Helper where it can find 
 *  Python.
 *  
 *  Usage: 
 *  
 *  setup() checks to see if the seeder is configured and setup the data
 *  directories, etc.
 *  
 *  setupHelpMessage() returns an error message explaining the last
 *  failure of setup()
 *  
 *  spawn($torrentfile) starts seeding a file
 *  
 *  pause($torrentfile) stops seeding a file
 *  
 *  stop($torrentfile) stops seeding a file and deletes the cached copy
 */

include_once "include.php";

class ServerSideSeeder {

  /**
   * constructor
   */
  function ServerSideSeeder() {
    $this->enabled = false;
    $this->problem = "";
    $this->supported_platforms = array("linux-386");
  }


		
  /**
   * Unpacks a zipfile to the $prefix directory
   * private function
   */
  function unzipFile( $file, $prefix = "data" ) {
	
		$file = dirname($_SERVER['SCRIPT_FILENAME']).'/'.$file;
		$zip = zip_open($file);
		
		if ($zip) {
			while ($entry = zip_read($zip)) {
		
				$name = zip_entry_name($entry);
				$size = zip_entry_filesize($entry);
		
				$dir = dirname($name);
		
				$full_curdir = '';
		
				if ($dir != '.') {
					foreach (explode('/',$dir) as $curdir) {
		
						if (!strlen($full_curdir))
							$full_curdir = $curdir;
						else
							$full_curdir .= '/'.$curdir;
		
						if (!file_exists($prefix.'/'.$full_curdir))
							mkdir($prefix.'/'.$full_curdir);	
					}
				}
	
				if (substr($name,strlen($name)-1,1) == '/') {	
					mkdir($prefix.'/'.$name);	
				}
				else if (zip_entry_open($zip,$entry,"rb")) {
					$fp = fopen($prefix.'/'.$name,"wb");
					
					fwrite($fp,zip_entry_read($entry,$size),$size);
					
					fclose($fp);
					
					zip_entry_close($entry);
		
				}
		
			}
		
			zip_close($zip);
			
			return true;
		
		} 
		else {
			return false; //This version of PHP doesn't support zip	
		}
	
	}


  /**
   * determine if server side seeding is enabled
   * @returns true if enabled, otherwise false
   */
  function enabled() {
    return $this->enabled;
  }


	/**
	 * try and extract a copy of the seeder code - using tar now instead of zip just
	 * because it's virtually guaranteed to be on a unix box
	 */
	function unzipBT() {

		$old_error_level = error_reporting(0);

		global $data_dir;

		// move the tar into the data dir
		if ( ! file_exists($data_dir . "/bt") ) {
			@exec("tar xvf btseeder.tar -C data");
		}
		error_reporting($old_error_level);

		if ( ! file_exists($data_dir . "/bt") ) {
			return false;
		}
		else {
			return true;		
		}

	}

	/**
	 * try and extract a copy of python
	 */
	function unzipPython() {
    if ( file_exists("python.zip") ) {
  		return $this->unzipFile("python.zip");
    }
    return false;
	}

  function validPython($version) {
    preg_match('/Python (\d).(\d)(.(\d))?/', $version, $res);
    if ( count($res) > 2 ) {
      $major = $res[1];
      $minor = $res[2];


      return $major > 2 || $minor >= 3;
    }

    return false;
  }

	/**
	 * Try and find a copy of python we can use to run the seeder
	 *
	 * this function defaults to trying to find a pre-installed version, but if that
	 * fails, it'll try and install our included, tarred version
	 */
	function findPython() {
	
		global $store;
		global $settings;
		
		if (isset($settings["sharing_python"]) && strlen($settings["sharing_python"])) {

			$version = @exec($settings["sharing_python"]." -V 2>&1");

			//if (preg_match('/^Python/',$version)) {
			if ( $this->validPython($version) ) {
				$settings["sharing_actual_python"] = $settings["sharing_python"];	
				$store->saveSettings($settings);
				return $settings["sharing_python"];
			}
		}
	
		//
		// if we've already figured out what we're sharing and saved it to our settings, then
		// just return that value
		//
		if (strlen($settings["sharing_actual_python"])) {
			return $settings["sharing_actual_python"];
		}

		//
		// otherwise, let's start out by trying to run a version already installed
		// on the server.  python tends to hold onto old copies with 'python' symlinked
    // to the newest version, but sometimes it'll be linked to an older version, so
    // we will iterate through several possible binaries until we find one which works
		//
    $pythons = array("python", "python2.4", "python2.3", "python2");

    foreach($pythons as $p) {
      $version = @exec("$p -V 2>&1");
	
      //		if (preg_match('/^Python/',$version)) {
      if ( $this->validPython($version) ) {
        $settings["sharing_actual_python"] = $p;
        $store->saveSettings($settings);
        return $p;
      }
    }

		//
		// if that fails, try running our included version of python
		//
		$prefix = dirname($_SERVER['SCRIPT_FILENAME']);

		foreach ($this->supported_platforms as $platform) {
			$version = exec("$prefix/data/python/$platform/python -V 2>&1");

			if (preg_match('/^Python/', $version)) {
				$settings["sharing_actual_python"] = 
          "PYTHONHOME=$prefix/data/python/$platform PYTHONPATH=$prefix/data/python/$platform $prefix/data/python/$platform/python";
	
				$store->saveSettings($settings);	
				return $settings["sharing_actual_python"];
			}
	
		}

		//
		// struck out, return null
		//
		return null;

	}



  /**
   * display a help message telling the user what they need to do to activate sharing
   */
  function setupHelpMessage() {
	
		if ($this->problem == "mkdir") {
	
	  		$output = "<p>Broadcast Machine Helper doesn't have permission to make the server sharing directory automatically. You need to make a writable directory named \"files\" in the data directory. On a typical web server, you might do this by connecting with your ftp client and typing the following commands:</p>\n";
	
        $permstr = "" . FOLDER_PERM_LEVEL;
        $output .= "<pre>\n";
        $output .= "cd ".preg_replace('|^(.*[\\/]).*$|','\\1',$_SERVER['SCRIPT_FILENAME'])."data\n";
        $output .= <<<EOD
	
	mkdir files
	
	chmod $permstr files
	
	</pre>
	
	<p>Note that giving the directories "777" permissions will allow
	anyone on the server to full access those directories. If you share a
	server with others, they may be able to tamper with you Broadcast Machine Helper
	data files if you use these settings. There may be other settings more
	appropriate for your server. <b>Please, contact your system administrator
	if you have any questions about permissions.</b></p>
	
EOD;
	
		} 
		else if ($this->problem == "unzip") {
		
			$output = <<<EOD
	
	<p>Broadcast Machine Helper cannot unzip the server BitTorrent client. Usually, this is because you are using a version of PHP without zip file support included. You need to unzip "btseeder.zip" and "python.zip" then upload them to the data directory. On a typical web server, you might do this by connecting with your ftp client from the directory with the unzipped files and typing the following commands:</p>
	
	<pre>
	
EOD;
	
			$output .= "cd ".preg_replace('|^(.*[\\/]).*$|','\\1',$_SERVER['SCRIPT_FILENAME'])."data\n";
			$output .= <<<EOD
	
	prompt n
	mput bt
	mput python
	
EOD;
	
			foreach ($this->supported_platforms as $platform) {
				$output .= "chmod 755 python/$platform/python\n";
			}
		
			$output .= "</pre>\n";
		} 
		else if ($this->problem == "permissions") {
		
			$output = <<<EOD
	
	<p>Broadcast Machine Helper does not have permission to execute the included Python interpreters. You need to change the permissions on the files. On a typical web server, you might do this by connecting with your ftp client and typing the following commands:</p>
	
	<pre>
	
EOD;
	
			$output .= "cd ".preg_replace('|^(.*[\\/]).*$|','\\1',$_SERVER['SCRIPT_FILENAME'])."data\n";
		
			foreach ($this->supported_platforms as $platform) {
				$output .= "chmod 755 python/$platform/python\n";
			}
		
			$output .= "</pre>\n";
		
		} 
		else if ($this->problem == "python") {
		
			$output = <<<EOD
	
	<p>Broadcast Machine Helper could not find a working Python interpreter. Please, specify the location of the python interpreter on your server below. Typical locations are "/usr/bin/python" and "/usr/local/bin/python". Please, contact your system administrator if you need help.</p>
	
EOD;
	
		} 
		else {
			$output = "";
		}
		
		return $output;
		
	}



	/**
	 * do some basic setup - make sure we have python, the seeder 
   * has been extracted, files created, etc, etc 
	 */
	function setup() {

		global $store;	
		global $settings;
		global $data_dir;
	
		$this->enabled = false;
    debug_message("seeder->setup()");

		// if we haven't tried installing the tracker yet, then
		// go ahead and try - if it works, we'll automatically turn it
		// on (global sharing is still off at this point)
		if ( !file_exists("$data_dir/bt") ) {
      debug_message("seeder: bt not installed yet, lets try");
      if ( $this->unzipBT() ) {
        debug_message("seeder: success!");
			  $settings["sharing_enable"] = true;
			  $store->saveSettings($settings);
      }
      else {
        debug_message("seeder: error in unzipBT");
        $this->problem = "unzipBT";
        return false;
      }
		}

    debug_message("seeder: bt code is installed");

		//
		// if we're not supposed to be running, then no point in setting things up
		//
		if (!$settings["sharing_enable"]) {
      debug_message("seeder: seeder hasn't been enabled by user, exiting");
			$this->problem = "disabled";
			return false;
		}
	
		$old_error_level = error_reporting(0);
	
		// check to see if all our folders are made
    make_folder($data_dir);
    make_folder("$data_dir/seedfiles");

		if ( ! is_writable($data_dir . '/seedfiles') ) {
      debug_message("seeder: couldnt create directories");
			$this->problem = "mkdir";
			return false;
		}
	
	
		// look to see if the tracker has been unzipped
		/*if ( !file_exists($data_dir . '/bt') && !$this->unzipBT() ) {
			$this->problem = "unzip";
			return false;
		}*/
	
		// do we have python?
		$this->python = $this->findPython();
    debug_message("seeder: python is " . $this->python);
	
		// if not, try and unzip it
		if ( !$this->python ) {
      debug_message("seeder: no python yet, try to unzip our copy");
      if ( !file_exists("$data_dir/python") && !$this->unzipPython() ) {
        debug_message("seeder: unzip failed");
				$this->problem = "unzip";
				return false;
			}
		
			foreach ( $this->supported_platforms as $platform ) {
				if ((!is_executable($data_dir . "/python/$platform/python")) && (!chmod($data_dir . "/python/$platform/python",0755))) {
          debug_message("seeder: python permissions error");
					$this->problem = "permissions";
					return false;
				}	
			}
		}
		
		// write out our .htaccess file to prevent direct access to seed files

		if (!file_exists($data_dir . '/seedfiles/.htaccess')) {
      write_deny_htaccess("$data_dir/seedfiles");
		}
		
		error_reporting($old_error_level);
		
		// at this point, if we have python, we're all set
		if ($this->python != null) {
      debug_message("seeder: should be all set");
			$this->problem = "";
			$this->enabled = true;
			return true;
		} 
		
		// otherwise, return false
		else {
      debug_message("seeder: still no python to use, failing");
			$this->problem = "python";
			return false;
		}
	
	}



  /**
   * figure out the status of the specified file
   *
   * if the torrent hasn't been updated in $update_interval seconds,
   * then it is assumed that it's not running anymore
   * @returns array of information
   */
   function getSpawnStatus($hash, $update_interval = 15) {

     //debug_message("getSpawnStatus for $hash");
	
     global $data_dir;
	
     if (!file_exists($data_dir . "/$hash.status")) {
       //debug_message("no status file");
       return array();
     }
	
     $data = array();
     $fp = fopen($data_dir . "/$hash.status","rb");
     flock($fp,LOCK_EX);
	
     while ($line = fgets($fp, 4096)) {
       $key = preg_replace("/^\s*(.*?)\s*?:.*/s",'\\1',$line);
       $value = preg_replace("/^.*:\s*(.*)\s*$/s",'\\1',$line);
       $data[$key] = $value;
     }
	
     flock($fp,LOCK_UN);
     fclose($fp);
     
     //debug_message("get stats");
     $stats = stat("$data_dir/$hash.status");

     $data["Last Update"] = $stats[9]; //Last modification time
     $data["Running"] = (time() - $stats[9] <= $update_interval);
	
     return $data;
   }


	/**
	 * check if the seeder was running.  if it wasn't and we didn't need it to, then
	 * return true, otherwise return false
	 * @returns true if running, false otherwise (but it also starts it running on false)
	 */
	function confirmSeederRunning($hash, $file) {
		$data = $this->getSpawnStatus($hash);

		// it's not running, but it shouldnt be
		if ( ! isset($data["Running"]) || $data["Running"] == true ) {
			return true;
		}

		$this->spawn($file);
		return false;
	}

  /**
   * stop the given pid which should be a torrent seeder
   *
   * does not do locking, nor does it remove files
   */
  function stop_by_pid($pid) {
	
		$retries = 0;
		$pid = (integer)$pid;

		// try a couple times to kill this pid
		while ( $retries < 3 && is_process_running($pid) ) {	
      //debug_message("kill $pid");
			if ( $pid > 0 ) {
				@posix_kill($pid, 2); // SIGINT
				sleep(10);
				@posix_kill($pid, 9); // SIGKILL
			}
			$retries++;
		}

	}



	/**
	 * stop an array of pids
	 *
	 * does not do locking, nor does it remove files
	 */
	function stop_by_pid_array($pids) {
	
		foreach ($pids as $pid) {
			$pid = (integer)$pid;
			if ( $pid > 0 ) {
        //debug_message("sigint $pid");
				@posix_kill($pid,2); //SIGINT
			}
		}
	
		sleep(10);
	
		foreach ($pids as $pid) {
			$pid = (integer)$pid;
			if ( $pid > 0 ) {
        //debug_message("sigkill $pid");
				@posix_kill($pid,9); //SIGKILL
			}
		}
	}



	/**
	 * stop an array of torrents
	 */
	function stop_array($torrents) {

		global $store;
		global $data_dir;
		global $torrents_dir;

		$pids = array();
		$delete = array();

    //debug_message("stop_array");
	
		$fp = fopen( $data_dir . "/spawnlock","wb");
		flock($fp,LOCK_EX);
	
    //debug_message("here");

		foreach ($torrents as $torrentfile) {
      //debug_message("*** $torrentfile");
      if ( file_exists($torrents_dir . "/$torrentfile") ) {
        $torrentfile = $torrents_dir . "/$torrentfile";
        //debug_message("bdecode $torrentfile");
        $torrent = bdecode(file_get_contents($torrentfile));
        //debug_message("done");
        
        if (is_array($torrent)) {
          $stats = $this->getSpawnStatus($torrent["sha1"]);
          //debug_message("got spawn status");

          if (count($stats) > 0) {
            $pids[] = $stats["process id"];
          }
          //          debug_message("check for file to delete");
          if (!preg_match('/(\/|^\.\.)/',$torrent["info"]["name"]) && file_exists($data_dir . "/seedfiles/" . $torrent["info"]["name"]) ) {
            //debug_message($data_dir . "/seedfiles/" . $torrent["info"]["name"]);
            $delete[] = $data_dir . "/seedfiles/" . $torrent["info"]["name"];
          }
          
          if ( file_exists($data_dir . "/" . $torrent["sha1"] . ".status") ) {
            //debug_message("add status file to delete queue");
            $delete[] = $data_dir . "/" . $torrent["sha1"] . ".status";
          }
        }
      }
      else {
        //debug_message("torrent $torrentfile doesn't exist?");
      }
    }

    //debug_message("call stop_by_pid_array");
		$this->stop_by_pid_array($pids);

		foreach ($delete as $delme) {
      //debug_message("delete $delme");
			$this->recursive_remove($delme);
		}

		flock($fp,LOCK_UN);
		fclose($fp);        
	
	}


	/**
	 * Recursively removes a directory and all of the files in it
	 */
	function recursive_remove($dir) {
	
		if (file_exists($dir)) {
			if (is_file($dir)) {
				unlink_file($dir);
			} 
			else {
				$handle = opendir($dir);

				while (false != ($file = readdir($handle))) {
					if (($file != '.') && ($file != '..'))
						$this->recursive_remove($dir.'/'.$file);
				}
	
				closedir($handle);
        //debug_message("rmdir $dir");
				rmdir($dir);
			}
		}
	}

	
	
	/**
	 * stop all seeder processes
	 */
	function stop_seeding() {

		global $store;
	
		$torrents = array();
    //debug_message("get list of torrents");
		$files = $store->getTorrentList();
	
		foreach ($files as $torrentfile) {
			if (($torrentfile != '.') && ($torrentfile != '..') && ($torrentfile != '.htaccess')) {
        //debug_message($torrentfile);
				$torrents[] = $torrentfile;
			}
		}

		$this->stop_array($torrents);
	
		//Erase any seeded files we might have missed
		global $data_dir;
		$handle = opendir($data_dir . '/seedfiles/');

		while (false !== ($file = readdir($handle))) {
			if (($file != '.') && ($file != '..') && ($file != '.htaccess')) {
				$this->recursive_remove($data_dir . "/seedfiles/$file");
			}
		}
	
		closedir($handle);
	
	}
	
	
	
	/**
	 * pause a torrent share
	 *
	 * this stops the process, but doesn't remove files, so it can be restarted later
	 * without too much hassle
	 */
	function pause($torrentfile) {

		global $data_dir;
		global $torrents_dir;

		if ( file_exists("$torrents_dir/$torrentfile") ) {	

			$fp = fopen($data_dir . "/spawnlock","wb");
			flock($fp,LOCK_EX);    
		
			$torrentfile = "$torrents_dir/$torrentfile";
			$torrent = bdecode(file_get_contents($torrentfile));
		
			if (!is_array($torrent)) {
				flock($fp,LOCK_UN);
				fclose($fp);
				return false;
			}
			
			$fp2 = fopen($data_dir . "/" . $torrent["sha1"] . ".paused", "wb");
			fwrite($fp2, time() );
			fclose($fp2);
		
			$stats = $this->getSpawnStatus($torrent["sha1"]);
			if ( isset($stats["process id"]) ) {
				$this->stop_by_pid($stats["process id"]);
			}

			// remove this file - that will cause us to stop tracking stats
			@unlink_file($data_dir . "/". $torrent["sha1"] . ".status");
	
			flock($fp,LOCK_UN);
			fclose($fp);
		}	
	}
	
	
	/**
	 * stop a torrent share
	 *
	 * this stops the process, and if delete_files is true, it also deletes the seedfiles
	 */
	function stop($torrentfile, $delete_files = true ) {
	
		global $data_dir;
		global $torrents_dir;

		if ( file_exists("$torrents_dir/$torrentfile") ) {	
			$this->pause( $torrentfile );

			$torrentfile = "$torrents_dir/$torrentfile";
			$torrent = bdecode(file_get_contents($torrentfile));
			@unlink_file($data_dir . "/" . $torrent["sha1"] . ".paused");

			if ( $delete_files == true ) {
	
				$fp = fopen($data_dir . "/spawnlock", "wb");
				flock($fp,LOCK_EX);    
			
				if ( is_array($torrent) && !preg_match('/(\/|^\.\.)/',$torrent["info"]["name"])) {
					$this->recursive_remove($data_dir . "/seedfiles/".$torrent["info"]["name"]);
				}	
				
				flock($fp,LOCK_UN);
				fclose($fp);
			}

		}
	}

	/**
	 * start a torrent share
	 */
	function spawn($torrentfile) {

		global $data_dir;
		global $torrents_dir;

		$update_interval = 15; //Seconds between updates

		$fp = fopen($data_dir . "/spawnlock","wb");
		flock($fp,LOCK_EX);    
	
		$torrentfile = "$torrents_dir/$torrentfile";

		// paranoia check - make sure the file exists	- if not, nothing to spawn
		if ( !file_exists($torrentfile) ) {
			return false;
		}

		$torrent = bdecode(file_get_contents($torrentfile));
	
		if (!is_array($torrent)) {
			flock($fp,LOCK_UN);
			fclose($fp);
			return false;
		}

		// we're spawning - make sure we don't have the .paused file still
		if ( file_exists($data_dir . "/" . $torrent["sha1"] . ".paused") ) {
				@unlink_file($data_dir . "/" . $torrent["sha1"] . ".paused");
		}
	
		$stats = $this->getSpawnStatus( $torrent["sha1"], $update_interval );

    //debug_message("seeding $torrentfile");
		if ( count($stats) == 0 || !$stats["Running"] ) {

			// if it's already running, then we're all set
			if ( isset($stats["process id"]) && is_process_running($stats["process id"]) ) {
 //       debug_message("$torrentfile already running " . $stats["process id"] );
				return true;
			}

			$statusfile = $data_dir . "/" . $torrent["sha1"] . ".status";
			$savein = $data_dir . "/seedfiles/";

			//global $minport;
			//global $maxport;
      global $settings;
      $minport = isset($settings["minport"]) ? $settings["minport"] : 6881;
      $maxport = isset($settings["maxport"]) ? $settings["maxport"] : 6889;
			
      if ( $maxport < $minport ) {
        $maxport = $minport + 8;
      }

			$command = $this->python . " $data_dir/bt/btdownloadbg.py \"$torrentfile\" --minport $minport --maxport $maxport --statusfile $statusfile --display_interval $update_interval --save_in $savein 2>&1";
			
      debug_message($command);

			$old_error_level = error_reporting(0);
			passthru($command);
			error_reporting($old_error_level);
			
			$result = true;
		} 

		//It's already running
		else {
			$result = false;
		}

		flock($fp, LOCK_UN);
		fclose($fp);
		return $result;
	
	}   

  function seedFiles() {
    global $store;
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
        } // if

      } // if local torrent

    } // foreach

  } // seedFiles


	/**
	 * create a torrent using the specified file which should be in the data directory
	 */
	function createTorrent($datafile, $unlink_original = false) {

		global $data_dir;
		global $torrents_dir;

		$fp = fopen("$data_dir/spawnlock", "wb");
		flock($fp, LOCK_EX);    

    $torrentfile = basename($datafile) . ".torrent";
		$torrentfile = "$torrents_dir/$torrentfile";
    @unlink($torrentfile);

    global $data_dir;
    $save_in = $data_dir . "/seedfiles/";

    if ( ! file_exists($save_in . basename($datafile) ) ) {
      debug_message("copy $datafile to $save_in" . basename($datafile) );
      $result = copy( $datafile, $save_in . basename($datafile) );

      if ( $unlink_original == true ) {
        @unlink($datafile);
      }

      $datafile = $save_in . basename($datafile);

    }


    $announce_url = get_base_url() . "announce.php";
    $command = $this->python . " $data_dir/bt/btmaketorrent.py --target \"$torrentfile\" $announce_url $datafile 2>&1";
    debug_message($command);

    $old_error_level = error_reporting(0);
    passthru($command);
    error_reporting($old_error_level);

		flock($fp,LOCK_UN);
		fclose($fp);

    $result = file_exists($torrentfile);
		return $result;
	}   

}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>