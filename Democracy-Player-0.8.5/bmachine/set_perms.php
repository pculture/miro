<?php
/**
 * set folder permissions using FTP
 * @package BroadcastMachine
 */


global $skip_setup;
$skip_setup = 1;

require_once("include.php");
require_once("ftp.php");

//
// only allow this code to be executed if the site hasn't been initialized yet
//
if ( check_permissions() != true && check_folders() != true ) {

  bm_header("Setup Broadcast Machine");
?>
<div class="page_name">
   <h2>Setup Broadcast Machine - FTP</h2>
</div>

<div class="section">

<?php
  $hostname = "localhost";
  $username = $_POST["username"];
  $password = $_POST["password"];
  $pwd = $_POST["ftproot"];


  //
  // generate a list of potential webroots
  //
  $folders = array_reverse( explode("/", $pwd) );
  $webroots = array();

  // always try what the user gave us first - this will either be the filesystem's reported path
  // to setup_help.php, or it will be a path the user entered
  $webroots[] = $pwd;

  $chunk = "";
  foreach($folders as $tmp) {
    if ( $tmp != "" ) {
      $chunk = "$tmp/$chunk";
      $webroots[] = "/$chunk";
    }
  }
  $webroots = array_reverse($webroots);
  
  $ftp = new FTP($hostname);
  
  ob_start();
	
  if($ftp->connect()) {
    $ftp->is_ok();
    
    if ( ! $ftp->login($username, $password) ) {
  ?>
	<h3>Oops!</h3>
	<p>Looks like there was a problem with the login information you specified.  Please
	back up and try again, or if you prefer, you can use one of the other options
	to set your permissions.</p>
	
  <?php
     exit;
    }
	

    // try each possible web root
    $good_path = false;
    foreach( $webroots as $pwd ) {
      if ( $ftp->cwd($pwd) ) {
	$good_path = true;
	break;
      }
    }

    if ( ! $good_path ) {
      print "
	<h3>Oops!</h3>
	<p>Looks like there was a problem with the directory you specified.  Please
	back up and try again, or if you prefer, you can use one of the other options
	to set your permissions.</p>";
      exit;
    }
		
    $ftp->is_ok();
    ob_flush();
	
    $ftp->mkd("data");	
    $ftp->is_ok();
    ob_flush();

    $ftp->mkd("data/seedfiles");	
    $ftp->is_ok();
    ob_flush();
	
    $ftp->mkd("torrents");	
    $ftp->is_ok();
    ob_flush();
	
    $ftp->mkd("publish");	
    $ftp->is_ok();
    ob_flush();
	
    $ftp->mkd("text");	
    $ftp->is_ok();
    ob_flush();
	
    $ftp->mkd("thumbnails");	
    $ftp->is_ok();
    ob_flush();


    $permstr = FOLDER_PERM_LEVEL;
	
    $ftp->chmod("data", $permstr);
    $ftp->is_ok();
    ob_flush();

    $ftp->chmod("data/seedfiles", $permstr);
    $ftp->is_ok();
    ob_flush();
	
    $ftp->chmod("torrents", $permstr);
    $ftp->is_ok();
    ob_flush();
	
    $ftp->chmod("publish", $permstr);
    $ftp->is_ok();
    ob_flush();
	
    $ftp->chmod("thumbnails", $permstr);
    $ftp->is_ok();
    ob_flush();
	
    $ftp->chmod("text", $permstr);
    $ftp->is_ok();
    ob_flush();
	
    //    header('Location: ' . get_base_url() . 'index.php');
	
  }
  else {
    print "Unable to connect!";
  }
?>  
<br><br>
<a href="admin.php">Continue</a> to make your first account.
</div>

<?php
  bm_footer();
}
else {
  header('Location: ' . get_base_url() . 'index.php');
}

?>