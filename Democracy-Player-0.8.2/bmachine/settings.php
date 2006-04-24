<?php
/**
 * admin page for managing settings
 * @package Broadcast Machine
 */

require_once("include.php");

if (!is_admin()) {
	header('Location: ' . get_base_url() . 'admin.php');
	exit;
}

global $settings;
global $store;
global $seeder;

$mod_write_result = true;
$rewrite_rss = false;

bm_header();

if ( isset($settings["use_mod_rewrite"]) && $settings["use_mod_rewrite"] == true &&  ( !file_exists(".htaccess") || filesize(".htaccess") <= 0 ) ) {
  $mod_write_result = write_mod_rewrite(true);
  $rewrite_rss = true;
} 

if (isset($_POST['title'])) {
	$title = encode($_POST['title']);
} 
else {
	$title = isset($settings['title'])?$settings['title']:'';
}

if (isset($_POST['theme'])) {
	$theme = encode($_POST['theme']);
} 
else {
	$theme = isset($settings['theme']) && $settings['theme'] != "" ? $settings['theme'] : 'classic';
}


if (isset($_POST['description'])) {
	$description = encode($_POST['description']);
} 
else {
	$description = isset($settings['description'])?$settings['description']:'';
}

if (isset($_FILES["image_upload"]) && $_FILES["image_upload"]["size"] > 0 ) {
	global $thumbs_dir;

	if (!file_exists($thumbs_dir)) {
		mkdir($thumbs_dir, $perm_level);
	}

	if (move_uploaded_file($_FILES['image_upload']['tmp_name'], "$thumbs_dir/" . $_FILES['image_upload']['name'])) {
		chmod("$thumbs_dir/" . $_FILES['image_upload']['name'], 0644);
		$image = "$thumbs_dir/" . $_FILES['image_upload']['name'];
	}
}
else if (isset($_POST['image'])) {
	$image = encode($_POST['image']);
} 
else {
	$image = isset($settings['image']) ? $settings['image'] : '';
}

if (isset($_POST['sharing_python'])) {
	$sharing_python = $_POST['sharing_python'];
} 
else {
	$sharing_python = isset($settings['sharing_python'])?$settings['sharing_python']:'';
}

if (isset($_POST['mysql_host'])) {
	$mysql_host = $_POST['mysql_host'];
} 
else {
	$mysql_host = isset($settings['mysql_host'])?$settings['mysql_host']:'';
}

if (isset($_POST['mysql_username'])) {
	$mysql_username = $_POST['mysql_username'];
} 
else {
	$mysql_username = isset($settings['mysql_username'])?$settings['mysql_username']:'';
}

if (isset($_POST['mysql_database'])) {
	$mysql_database = $_POST['mysql_database'];
} 
else {
	$mysql_database = isset($settings['mysql_database'])?$settings['mysql_database']:'';
}

if (isset($_POST['mysql_password'])) {
	$mysql_password = $_POST['mysql_password'];
} 
else {
	$mysql_password = isset($settings['mysql_password'])?$settings['mysql_password']:'';
}

if (isset($_POST['mysql_prefix'])) {
	$mysql_prefix = $_POST['mysql_prefix'];
} 
else {
	$mysql_prefix = isset($settings['mysql_prefix'])?$settings['mysql_prefix']:'';
}

if ( !isset($settings["use_mod_rewrite"]) ) {
  $settings["use_mod_rewrite"] = false;
}

if ( count($_POST) > 0 ) {
	$sharing_enable = ((isset($_POST['sharing_enable']) && ($_POST['sharing_enable']=="1")));
	$sharing_auto = ((isset($_POST['sharing_auto']) && ($_POST['sharing_auto']=="1")));
	$use_mod_rewrite = ((isset($_POST['use_mod_rewrite']) && ($_POST['use_mod_rewrite']=="1")));

	if ( $use_mod_rewrite != $settings["use_mod_rewrite"] ) {
		$mod_write_result = write_mod_rewrite($use_mod_rewrite);
		$rewrite_rss = true;
	}
} 
else {
	$sharing_enable = $settings["sharing_enable"];
	$sharing_auto = $settings["sharing_auto"];
	$use_mod_rewrite = $settings["use_mod_rewrite"];
}

$newsettings = array();

foreach ($settings as $settingname => $value) {
	$newsettings[$settingname] = $value;
}

$newsettings['title'] = $title;
$newsettings['description'] = $description;
$newsettings['image'] = $image;
$newsettings['theme'] = $theme;


$newsettings['sharing_enable'] = $sharing_enable;
$newsettings['sharing_auto'] = $sharing_auto;
$newsettings['sharing_python'] = $sharing_python;
$newsettings['mysql_host'] = $mysql_host;
$newsettings['mysql_database'] = $mysql_database;
$newsettings['mysql_username'] = $mysql_username;
$newsettings['mysql_password'] = $mysql_password;
$newsettings['mysql_prefix'] = $mysql_prefix;
$newsettings['use_mod_rewrite'] = $use_mod_rewrite;


// Stop seeding everything if sharing is turned off
if ($settings['sharing_enable'] && !$newsettings['sharing_enable']) {
	$seeder->stop_seeding();
}

// If the python field has changed, find the python interpretter again
if ($settings['sharing_python'] != $newsettings['sharing_python']) {
	$newsettings['sharing_actual_python'] = '';
	$settings['sharing_actual_python'] = '';
	$seeder->setup();
}


if ( isset($_POST["post_show_default"]) ) {
	if( $_POST["post_show_default"] == '1' ) {
		$newsettings["DefaultChannel"] = '';
	} 
	else {
		$newsettings["DefaultChannel"] = $_POST["channels"];
	}
}

// Used to determine if we need to re-setup server side seeding after a
// settings change
$was_sharing = $settings['sharing_enable'];

if ( count($_POST) > 0 ) {

	$result = $store->saveSettings($newsettings);

	//Re-setup sharing if the setting has changed
	if ($settings['sharing_enable'] != $was_sharing) {
		$seeder->setup();
	}

	//
	// Automagically change the backend if the database settings have changed
	//
	if ( strlen($newsettings['mysql_database']) ) {
		if ($store->type() != 'MySQL') {
			setup_data_directories(true);
		}
	}  // if
	else {
		if ($store->type() == 'MySQL') {
			setup_data_directories(true);
		}
	} // else

	if ( $rewrite_rss ) {
		// rewrite our RSS files with the proper URLs
		$channels = $store->getAllChannels();
		foreach ($channels as $channelID => $c) {
			makeChannelRss($channelID, false);
		}
	}

} // if ( $_POST )

$default_channel = isset($settings['DefaultChannel'])?$settings['DefaultChannel']:'';

?>

<div class="wrap">
<SCRIPT LANGUAGE="JavaScript">
<!-- Idea by:  Nic Wolfe (Nic@TimelapseProductions.com) -->
<!-- Web URL:  http://fineline.xs.mw -->

<!-- This script and many more are available free online at -->
<!-- The JavaScript Source!! http://javascript.internet.com -->

<!-- Begin
function popUp(URL) {
day = new Date();
id = day.getTime();
eval("page" + id + " = window.open(URL, '" + id + "','toolbar=0,scrollbars=1,location=0,statusbar=0,menubar=0,resizable=0,width=500,height=600');");
}
// End -->
</script>

<!-- BASIC PUBLISHING OPTIONS -->
<div class="page_name">
   <h2>General Settings</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/settings_popup.php')"><img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

<div class="section">
<?php
if ( count($_POST) > 0 ) {
  if ( $result == true ) {
    echo "<p>Changes Saved</p>";
  }
  else {
    global $errstr;
    echo "<p>Sorry, there was an error saving your settings: $errstr</p>";
  }
}
?>

<form action="settings.php" method="POST" name="frm" accept-charset="utf-8, iso-8859-1" enctype="multipart/form-data" >
<input type="submit" value="Save Settings >>" />

<div class="section_header">Website Information</div>
<p>Please enter a title and description for your installation of Broadcast Machine:</p>
<p>Title: <input type="textbox" name="title" value="<?php echo isset($settings['title']) ? $settings['title'] : ''; ?>" /></p>
<p>Description:<br />
<textarea name="description" wrap="soft" rows="5" cols="35">
<?php echo isset($settings['description'])?$settings['description']:''; ?>
</textarea>
</p>


<fieldset><div class="the_legend">Site Image: </div>
<p>This is a thumbnail which will appear on every page.  Please try and make the size about 48x48 pixels.</p>
<a href="#" onClick="document.getElementById('specify_image').style.display = 'none'; document.getElementById('upload_image').style.display = 'block'; return false;">Upload Image</a> or <a href="#" onClick="document.getElementById('upload_image').style.display = 'none'; document.getElementById('specify_image').style.display = 'block'; return false;">Specify URL</a>

<div style="display:none;" id="upload_image">
<input type="file" name="image_upload" value="Choose File" />
</div>

<div id="specify_image" style="display:<?php
if ($image == "" || $image == "http://") {
	echo "none";
} 
else {
	echo "block";
}
?>;" >
<input type="text" name="image" size="38" value="<?php echo $image; ?>"/>
</div>
</fieldset>

<div class="section_header">Front Page Display</div>
<p>Choose how you want the <a href="index.php">Front Page</a> of your Broadcast Machine to display:</p>


<ul>
<li>&nbsp;&nbsp;<input type="radio" name="post_show_default" value="0"<?php

	if ($default_channel != "") {

		print(" checked=\"true\"");

	}

?>/> Show the <select name="channels" onFocus="document.frm.post_show_default[0].checked = true;">

<?php

	$channels = $store->getAllChannels();
	foreach ($channels as $channelID => $channel) {

		print("<option value=\"" . $channelID . "\"");
		if ($channelID == $default_channel) {
			print(" selected");
		}
		print(">" . $channel["Name"] . "</option>");

	}
?>

</select>

 channel as the front page.</li>

<li>&nbsp;&nbsp;<input type="radio" name="post_show_default" value="1"<?php

	if ($default_channel == "") {
		print(" checked=\"true\"");
	}

?>/> Show a list of all channels and the 3 most recent files in each.</li>
</ul>

<br />


<div class="section_header">Direct URLs</div>

Enabling this setting makes your feeds compatible with iTunes and improves access for some search 
engines.  It works by changing the way the Broadcast Machine links to files with a "mod_rewrite"  
command.  It may not work on all servers-- you should test it by enabling the setting and then 
clicking on links to files on your front page.  If the links work, then everything is 
fine.  <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/settings_popup.php')">More info >></a>

<?php
if ( is_writable('.htaccess') == false ) {

	$output ="cd " . preg_replace( '|^(.*[\\/]).*$|', '\\1', $_SERVER['SCRIPT_FILENAME'] );
  $output .= "
touch .htaccess
chmod 777 .htaccess";
?>
<br />
<br />

In order to use this feature, you need to give Broadcast Machine access to the file '.htaccess'.  You can do 
this by logging into your server and entering the following commands:
<?php
	print "<pre>$output</pre>";
}
?>

<br />
<?php
   echo '<p><input type="checkbox" name="use_mod_rewrite" 
	 	value="1" '.(isset($settings['use_mod_rewrite']) && $settings['use_mod_rewrite'] ? "checked=\"true\" ":"")." /> Enable Direct URLs</p>\n";
?>

<br />

<?php
	global $themes_dir;
	$themes = dir($themes_dir);
	$choices = array();

  // load in a list of themes
	while(($themestr = $themes->read()) !== false) {	
		if ( $themestr != "." && $themestr != ".." ) {
			$choices[$themestr]["id"] = $themestr;
			if ( file_exists($themes_dir . "/" . $themestr . "/description.txt") ) {
				$choices[$themestr]["description"] = file_get_contents($themes_dir . "/" . $themestr . "/description.txt");
			}
			if ( file_exists($themes_dir . "/" . $themestr . "/icon.gif") ) {
				$choices[$themestr]["icon"] = $themes_dir . "/" . $themestr . "/icon.gif";
			}
		}
	} // while

	if ( count($choices) > 0 ) {
?>
<div class="section_header">Theme</div>
<p>Broadcast Machine comes with several themes to choose from.  Each one has its own distinct style.  You can
also create your own theme by following <a href="">these instructions</a></p>
<p>
Which theme would you like to use?
<br />
<ul>
<?php
		foreach($choices as $id => $tmptheme) {
			print "<li> <input type=\"radio\" name=\"theme\" value=\"$id\" ";
			if ( isset($theme) && $id == $theme ) {
				print " checked=\"true\" ";
			}
			print "/> $id";
			if ( isset($tmptheme["description"]) ) {
				print " - " . $tmptheme["description"];
			}
      print "</li>\n";
		}		
	}
?>
</ul>
</p>

<div class="section_header">Server-Sharing Settings</div>

<p>Broadcast Machine can share files from your server, as well as from your home computer. This increases 
performance and avoids firewall related slowdowns. Most importantly, once your server has a full copy 
of the file, you don't need to continue sharing the file from a personal computer-- there will 
always be at least one seed available. However, server-sharing also uses disk space and bandwidth 
on your server. You can choose to automatically server-share all files as they are uploaded 
or you can manually enable server sharing on a per-file basis. The status of server-sharing 
for a particular file appears in the 'Files' tab.</p>


<p>Linux, Mac OS X, and UNIX servers are supported. Most Linux servers should work without entering 
additional settings. If you have a Mac OS X or UNIX server, you'll need to tell Broadcast Machine Helper where 
it can find Python. Contact your system administrator if you need help.</p>


<p><b>REMEMBER:</b> if you turn on server sharing you must have enough diskspace to store 
each file the server is sharing and enough bandwidth to upload several copies of each file 
shared from the server. When you turn on server sharing, you can choose to start or stop 
sharing on any particular file. You may want to turn off server sharing for a particular file 
once there are enough seeds available on the network.</p>


<?php $seeder->setup(); ?>

<p>Server sharing is currently <?php if (!$seeder->enabled()) echo '<strong>NOT</strong> '?>functioning</p>

<?php

   echo $seeder->setupHelpMessage();

   echo '<p><input type="checkbox" name="sharing_enable" value="1" '.($settings['sharing_enable'] ? "checked=\"true\" ":"")." /> Enable server sharing</p>\n";

   echo '<p><input type="checkbox" name="sharing_auto" value="1" '.($settings['sharing_auto'] ? "checked=\"true\" ":"")." /> Automatically server share files</p>\n";

?>

<p>Location of Python Interpreter<br />
For example: <em>/usr/bin/python</em> (OS X and UNIX servers only):<br />
<?php
	if ( !isset($settings['sharing_python']) || $settings['sharing_python'] == "" ) {
		$settings['sharing_python'] = $seeder->findPython();
	}
?>
<input type="textbox" name="sharing_python" 
	value="<?php echo isset($settings['sharing_python'])?$settings['sharing_python']:''; ?>" />
</p>

<div class="section_header">MySQL Settings</div>

<p>Currently, this installation of Broadcast Machine Helper 
<?php 
if ( $store->type() != 'MySQL' ) {
  print "<strong>is NOT</strong> ";
}
else {
  print "<strong>IS</strong> ";
}
?>
using MySQL</p>


<?php
// check to see if there's a mysql error
global $mysql_error;
if ( $store->type() != 'MySQL' && count($_POST) > 0 && isset($mysql_error) ) {
  print "<p>Looks like there was an error trying to connect to MySQL: <em>$mysql_error</em></p>";
} 
?>


<p>MySQL is a database system which might be offered to you by your hosting provider.  It can be used to hold the data for your site, rather
than storing it in files on the server.  While it isn't needed for small Broadcast Machine sites, for larger/busier sites it can greatly improve 
performance.  If you want to use MySQL for Broadcast Machine, ask your provider for the information fields listed below and then enter them here:</p>

<p>Host name: <input type="textbox" name="mysql_host" value="<?php echo isset($settings['mysql_host'])?$settings['mysql_host']:'localhost'; ?>" /><br />
<small>If your provider didn't give you the hostname, it is probably 'localhost'.</small></p>

<p>Database: <input type="textbox" name="mysql_database" value="<?php echo isset($settings['mysql_database'])?$settings['mysql_database']:''; ?>" /><br />
<small>This is the name of the database - your provider will give you this information.</small></p>

<p>Username: <input type="textbox" name="mysql_username" value="<?php echo isset($settings['mysql_username'])?$settings['mysql_username']:''; ?>" /><br />
<small>Your MySQL login, which might not be the same as your FTP login.</small></p>

<p>Password: <input type="textbox" name="mysql_password" value="<?php echo isset($settings['mysql_password'])?$settings['mysql_password']:''; ?>" /><br />
<small>Your MySQL password, which might not be the same as your FTP password.</small></p>

<?php
if ( !isset($settings['mysql_prefix']) ) {
  $prefix = "bm_";
}
else {
  $prefix = $settings['mysql_prefix'];
}
?>

<input type="text" class="hidden" name="mysql_prefix" value="<?php print $prefix; ?>" />

<!--
<p>Table Prefix: <input type="textbox" name="mysql_prefix" value="<?php echo isset($settings['mysql_prefix'])?$settings['mysql_prefix']:''; ?>" /><br />
</p> 
-->

<input type="submit" value="Save Settings >>" />

<br /><br />
</div> <!-- closes section-->
</div> <!-- closes rap-->

<?php
	bm_footer();

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>