<?php
/**
 * 'dashboard' page for the backend of the site
 *
 * @package Broadcast Machine
 */

require_once("include.php");
require_once("version.php");

requireUserAccess();

if ( ! is_admin() ) {
	header("Location: " . get_base_url() );
	exit;
}

update_base_url();

function mycomp($a, $b) {
	return ($b["Created"] - $a["Created"]);
}

global $store;
$users = $store->getAllUsers();
$files = $store->getAllFiles();

bm_header();
?>


<div class="wrap">
<!-- BASIC PUBLISHING OPTIONS -->

<div class="page_name">
   <h2>Dashboard</h2>
</div>

<?php
	// check to see if the datastore version is the same as the stated version of BM -
	// if not, we will ask the user to upgrade
	if ( get_datastore_version() < get_version() ) {
?>
<h4 style="color: #c00">Time to Upgrade!</h4>
<p>
It looks like you've uploaded a new copy of Broadcast Machine.  Please <a href="upgrade.php">Click Here</a>
to do any required maintenance.
</p>

<?php
	}

	// do a check here to make sure we can write to the filesystem.  we
	// could do this globally, on every single page, but for security reasons,
	// this seems a little safer

	$folders = check_folders();
	$perms = check_permissions();


	if ( $perms || $folders ) {
?>

<h4 style="color: #c00">Setup Problem!</h4>
<p>For Broadcast Machine to work correctly, you need to

<?php if ( $folders ) {
?>
 create the following directories:</p>

<ul>
<?php
		foreach($folders as $error) {
			print "<li>$error</li>\n";
			$fixstr1 = "mkdir $error\n";
		}
?>
</ul>
<p>And 
<?php
	}
?>

edit the permissions for the following directories:</p>

<ul>
<?php
		foreach($perms as $error) {
			print "<li>$error</li>\n";
			$fixstr2 = "chmod 777 $error\n";
		}
?>
</ul>

<p>
You can fix this problem by connecting to your server using FTP, opening the folder where you installed Broadcast Machine and creating any missing folders.  Then set the permissions for the folders listed above to "readable", "writable" and "executable" for owner, group, and others.
</p>

<p>Or log on to your server and type:

<pre>
<?php
print "cd " . preg_replace( '|^(.*[\\/]).*$|', '\\1', $_SERVER['SCRIPT_FILENAME'] ) . "\n";

if ( isset($fixstr1) ) {
	print $fixstr1;
}
if ( isset($fixstr2) ) {
	print $fixstr2;
}

?>
</pre>
</p>

<?php
	}

	if ( check_access() ) {
?>

<h4 style="color: #c00">Security Problem!</h4>
<p>It looks like the data files for Broadcast Machine are accessible, which presents a 
security risk.  You should take steps to make sure that those files aren't downloadable.
</p>

<?php	
	}	
?>


<div id="alerts_activity">

<?php
if (is_admin()) {

	$pendingCount = 0;

	foreach ($users as $person) {
		if (isset($person['IsPending']) && $person['IsPending'] == 1 ) {
			$pendingCount++;
		}
	}

	if ($pendingCount > 0) {
?>

<div class="alerts">
<h4>Alerts</h4>
<ul>
<?php

		if ($pendingCount > 0) {
			print("<li>Users: <a href=users.php>" . $pendingCount . " Pending User");

			if ($pendingCount > 1) {
				print("s");
			}
			print(" </a></li>");
		}
?>
</ul>
</div>

<?php
	}
}
?>

<div class="activity">
<h4>Newly Registered Users</h4>

<?php
usort($users, "mycomp");
$i = 0;

foreach($users as $people) {
	if ($i < 3) {
?>

<div class="user_list_item">
	<div class="user_name"><?php echo $people["Name"]; ?></div>
	<div class="user_email"><?php
		if (is_admin()) {
			if (strlen($people["Email"]) > 20) {
				print(substr($people["Email"],0,18) . "...");
			} 
			else {
				print($people["Email"]);
			}
		}
	?></div>
</div>

<div class="spacer">&nbsp;</div>

<?php
		$i++;
	}
	else {
		break;
	}

}

if (is_admin()) {
?>

<div class="spacer">&nbsp;</div>
<a href="users.php">Go to Users</a>
<?php
}
?>

<h4>Recently Published</h4>
<?php
if ( !isset($files) ) {
	$files = array();
}
usort($files, "mycomp");

$i=0;

foreach($files as $hash => $file) {
	if ($i < 3) {
?>

<div class="user_list_item">
	<div class="edit_user"><?php
		print($file["Title"]);
	?></div>
</div>
<div class="spacer">&nbsp;</div>
<?php
		$i++;
	}
	else {
		break;
	}
}

if (is_admin()) {
?>

<div class="spacer">&nbsp;</div>
<a href="edit_videos.php">Go to Files</a>
<div class="spacer">&nbsp;</div><br /><br />
<h4><a href="index.php">View Front Page &gt;&gt;</a></h4>

<?php
}
?>
</div>

</div> <!-- alerts_activity -->

<div id="outside_info">

<IFRAME 
	FRAMEBORDER=0 id="pcf_upgrade" height="85" width="100%" border="0" 
	style="border: none; padding: 0; margin: 0;" 
	SRC="http://www.participatoryculture.org/bm_updates/check.php?v=<?php echo urlencode(get_version()); ?>">

Support Broadcast Machine, donate to continued development!

</IFRAME>

<IFRAME 
	FRAMEBORDER=0 id="pcf_news" height="280" width="100%" border="0" 
	style="border: none; padding: 0; margin: 0;" 
	SRC="http://participatoryculture.org/blog/bm_dashboard/dashboard.php">
</IFRAME>
</div> <!-- outside info -->

<?php
	bm_footer();
?>