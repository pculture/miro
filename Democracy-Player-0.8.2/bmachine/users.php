<?php
/**
 * page to list/manage users
 * @package Broadcast Machine
 */

require_once("include.php");


// don't allow non-admin access
if ( ! is_admin() ) {
	header("Location: " . get_base_url() . "index.php");
	exit;
}

global $settings;

//
// got some user data, save it
//
if (isset($_POST["username"])) {
	if ($_POST["pass1"] == $_POST["pass2"] && $_POST["pass1"] != "") {
		global $store;

		$username = trim(mb_strtolower( $_POST["username"] ));

		$result = $store->addNewUser(
			$username,
			$_POST["pass1"],
			encode($_POST["email"]),
			isset($_POST["admin"]), false, $error);
			
		if ( $result == false ) {
			// if we get here, there was a filesystem error or something like that
			$msg = "Your account could not be added. <strong>" . $error . "</strong>";		
		}
		else {
			$hashlink = sha1( $username . $_POST["pass1"] . $_POST["email"] );		
			$result = $store->authNewUser( $hashlink, $username );

			if ( $result == false ) {
				// if we get here, there was a filesystem error or something like that
				$msg = "Your account could not be added. <strong>" . $error . "</strong>";		
			}
			
		}

	}
}

global $store;
$users = $store->getAllUsers();
$channels = $store->getAllChannels();

//
// got new setting data, save it
//
if (isset($_POST["uploadReg"])) {
	$hasOpen = false;
	foreach ($channels as $channel) {
		if (isset($_POST["allow_" . $channel["ID"]])) {
			$hasOpen = true;
		}
		$channels[$channel["ID"]]["OpenPublish"] = isset($_POST["allow_" . $channel["ID"]]);
		$store->saveChannel($channel);
	}

	$settings['AllowRegistration'] = isset($_POST["allowReg"]);
	$settings['RequireRegApproval'] = isset($_POST["reqApproval"]);
	$settings['RequireRegAuth'] = isset($_POST["reqAuth"]);
	$settings['UploadRegRequired'] = $_POST["uploadReg"];
	$settings['DownloadRegRequired'] = $_POST["downloadReg"];
	$settings['HasOpenChannels'] = $hasOpen;

	$store->saveSettings($settings);
}


//
// don't allow a non-admin user to access this page unless the site hasn't been
// set up yet (users == 0)
//
if (!is_admin() && count($users) > 0) {
	header('Location: ' . get_base_url() . 'admin.php');
	exit;
}

bm_header();
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
<?php
	if ( isset($msg) && $msg != "") {
		print("<p class=\"error\">" . $msg . "</p>");
	} 
?>

<div class="page_name">
<h2>Users</h2>
<div class="help_pop_link">
  <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/settings_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
</div>
</div>

<h2>Admins</h2>

<?php
foreach ($users as $person) {
	if ($person['IsAdmin']) {
?>
		<div class="user_list_item">
			<div class="user_name"><?php echo $person['Name']; ?></div>
			<div class="user_email"><?php echo substr($person['Email'],0,12); ?>...</div>
			<div class="edit_user">
<?php print("<a href=\"user_edit.php?i=" . urlencode($person['Name'])  . "\">Edit</a>");
// don't let someone delete themself
if ( $person['Name'] != $_SESSION['user']['Name'] ) {
	print(" - <a href=\"user_edit.php?d=1&amp;i=" . urlencode($person['Name'])  . "\" onClick=\"return confirm('Are you sure you want to delete this user?');\">Delete</a>"); 
}
?>
 </div>
		</div>
		<div style="clear: both; font-size: 2px; height: 1px;">&nbsp;</div>
<?php
	}
}

print("<br /><br /><h2 class=\"page_name\">Registered Users</h2>");

$got_reg_user = false;

foreach ($users as $person) {
	if (!$person['IsAdmin'] ) {
		$got_reg_user = true;
?>
		<div class="user_list_item">
			<div class="user_name"><?php echo $person['Name']; ?></div>
			<div class="user_email"><?php echo substr($person['Email'],0,12); ?>...</div>
			<div class="edit_user"><?php
					if ($person['IsPending']) {
						print("<font color=red>PENDING</font> <a href=\"user_edit.php?a=1&amp;i=" . urlencode($person['Name'])  . "\">Approve</a> - ");
					}
					print("<a href=user_edit.php?i=" . urlencode($person['Name'])  . ">Edit</a>");
					
					// don't let someone delete themself
					if ( $person['Name'] != $_SESSION['user']['Name'] ) {
						print (" - <a href=\"user_edit.php?d=1&amp;i=" . urlencode($person['Name'])  . "\" onClick=\"return confirm('Are you sure you want to delete this user?');\">Delete</a>");
					}
			?></div>
		</div>

		<div style="clear: both; font-size: 2px; height: 1px;">&nbsp;</div>
<?php
	} // if ( ! isadmin )
} // foreach

if ( $got_reg_user == false ) {
	print "<div class=\"user_list_item\">None</div>\n";
}


?>

<br /><br />

<div class="half_float">
<h2 class="page_name">Add User</h2>

<div class="section">
<form action="users.php" method="post" name="newuser" accept-charset="utf-8, iso-8859-1">

<fieldset>
   <div class="the_legend">Email: </div><br /><input type="text" name="email" size="25" value=""/>
</fieldset>

<fieldset>
<div class="the_legend">Name / Alias: </div><br /><input type="text" name="username" size="25" value=""/>
</fieldset>

<fieldset>
   <div class="the_legend">Password: </div><br /><input type="password" name="pass1" size="25"  value=""/>
</fieldset>

<fieldset>
   <div class="the_legend">Password Again: </div><br /><input type="password" name="pass2" size="25" value=""/>
</fieldset>

<fieldset>
<input type="checkbox" name="admin" /> Make Admin
</fieldset>


<p class="publish_button" style="clear: both;">
<input style="border: 1px solid black;" type="submit" value="&gt;&gt; Add User" border=0 alt="Continue" />
</p>

</form>
</div>
</div>

<div class="half_float">
<form action="users.php" method="post" name="usersettings" accept-charset="utf-8, iso-8859-1">
<h2 class="page_name">User Settings</h2>
<div class="section">

<ul>
<li><input type="checkbox" name="allowReg"<?php if ($settings['AllowRegistration']) { echo " checked=\"true\""; } ?>/> Allow new users to register.</li>
<li><input type="checkbox" name="reqApproval"<?php if ($settings['RequireRegApproval']) { echo " checked=\"true\""; } ?>/> Require Approval for new users.</li>
<li><input type="checkbox" name="reqAuth"<?php if ($settings['RequireRegAuth']) { echo " checked=\"true\""; } ?>/> Require Email Authorization of new users.</li>
</ul>

<div class="section_header">Upload Settings</div>
<?php
if (count($channels) > 0) {
?>

<ul>
<li>Admins can always upload to any channel.  You can allow non-admins to post files to:</li>

<?php
	foreach ($channels as $channel) {

		print("<li>&nbsp;&nbsp;<input type=checkbox name=\"allow_" . $channel['ID'] . "\"");

		if ( isset($channel["OpenPublish"]) && $channel["OpenPublish"]) {
			print(" checked=\"true\"");
		}

		print("/> " . $channel['Name'] . "</li>");
	}
?>
</ul>

<?php
}
?>

<ul>
<li>For the channels that allow non-admins to post files:</li>
<li>&nbsp;&nbsp;<input type="radio" name="uploadReg" value="" <?php if (!$settings['UploadRegRequired']) { echo " checked=\"true\""; } ?>/> Anyone can upload</li>
<li>&nbsp;&nbsp;<input type="radio" name="uploadReg" value="1" <?php if ($settings['UploadRegRequired']) { echo " checked=\"true\""; } ?>/> Only registered users can upload</li>
</ul>

<div class="section_header">Download Settings</div>
<ul>
<li>&nbsp;&nbsp;<input type="radio" name="downloadReg" value="" <?php if (!$settings['DownloadRegRequired']) { echo " checked=\"true\""; } ?>/> Anyone can download</li>
<li>&nbsp;&nbsp;<input type="radio" name="downloadReg" value="1" <?php if ($settings['DownloadRegRequired']) { echo " checked=\"true\""; } ?>/> Only registered users can download</li>
</ul>

<p class="publish_button" style="clear: both;">
<input style="border: 1px solid black;" type="submit" value="&gt;&gt; Save Settings" border=0 alt="Continue" />
</p>

</div>
</form>
</div>

<?php
bm_footer();
?>