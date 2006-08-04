<?php
/**
 * create and upload a .htaccess file using FTP
 * @package BroadcastMachine
 */
require_once("include.php");

if (!is_admin()) {
  header('Location: ' . get_base_url() . 'admin.php');
  exit;
}

  bm_header("Setup Broadcast Machine");
?>
<div class="page_name">
   <h2>Setup Broadcast Machine - Friendly URLs</h2>
</div>

<div class="section">
<?php
if ( !isset($_POST["password"]) ) {
?>

Enter your FTP information into the form below:

<?php
$path = guess_path_to_installation();
?>
<p>
<form method="POST" action="generate_htaccess.php">
     FTP username: <input type="text" name="username" size="10" /><br />
     FTP password: <input type="password" name="password" size="10" /><br />
     Website Folder: <input type="text" name="ftproot" value="<?php print $path; ?>" size="50" /><br />
     <input type="submit" value="Go" />
</form>
</p>

<p>
<?php
bm_footer();
print "</div>";
exit;

}

global $skip_setup;
$skip_setup = 1;

require_once("include.php");
require_once("ftp.php");

$hostname = "localhost";
$username = $_POST["username"];
$password = $_POST["password"];
$pwd = $_POST["ftproot"];

// generate a list of potential webroots
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

$ftp = new FTP($hostname);

if( $ftp->connect() ) {
  $ftp->is_ok();
  
  if ( ! $ftp->login($username, $password) ) {
    bm_header();
  ?>
    <h3>Oops!</h3>
	<p>Looks like there was a problem with the login information you specified.  Please
	back up and try again, or if you prefer, you can use one of the other options
	to set your permissions.</p>
	
  <?php
     bm_footer();   
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
		

    // grab existing .htaccess file
    $text = generate_htaccess_text(true);

    // create .htaccess file
    file_put_contents("/tmp/.htaccess", $text);

    // upload it
    $ftp->is_ok();
    //$ftp->ascii();
    $ftp->stor("/tmp/.htaccess", "$pwd/.htaccess");
    ob_flush();
    $ftp->is_ok();

    $permstr = FOLDER_PERM_LEVEL;
    $ftp->chmod("$pwd/.htaccess", $permstr);
    $ftp->is_ok();

    // now that the file is written to the system, lets see if it actually works
    global $settings;
    global $store;
    if ( test_mod_rewrite() == true ) {
      $settings["use_mod_rewrite"] = true;
    }
    else {
      $settings["use_mod_rewrite"] = false;
    }
    $result = $store->saveSettings($settings);

    bm_footer();
?>

<br><br>
<a href="admin.php">Continue</a>
</div>
<?php
    exit;
    //header('Location: ' . get_base_url() . 'settings.php');
	
  }
  else {
    print "Unable to connect!";
  }

?>