<?php
/**
 * page for editing a user
 * @package Broadcast Machine
 */


require_once("include.php");

$is_mine = false;

if (isset($_SESSION['user']) && $_SESSION['user']) {

	if (isset($_GET["i"])) {
		$username = trim(mb_strtolower( $_GET["i"] ));
	} 
	else if (isset($_POST["username"])) {
		$username = trim(mb_strtolower( $_POST["username"] ));
	}

	if (mb_strtolower($_SESSION['user']['Name']) == $username) {
		$is_mine = true;
	}

}

//
// make sure that non-admins don't try and edit someone else
//
if (!is_admin() && !$is_mine) {
	header('Location: ' . get_base_url() . 'admin.php');
	exit;
}


//
// update the user
//
if (isset($_GET["a"])) {

	global $store;
	$users = $store->getAllUsers();
//	$update = $users[$_GET["i"]];
	$update = $users[$username];

	if ( isset($update) ) {
		$store->updateUser($username, $update["Hash"], $update["Email"], $update["IsAdmin"]);
	}

	header('Location: ' . get_base_url() . 'users.php');
	exit;
}

//
// delete the user
//
if (isset($_GET["d"]) && is_admin() ) {
	$store->deleteUser($username);

	global $store;
	$users = $store->getAllUsers();

	//
	// this will happen in the unlikely situation that all the users are deleted
	//
	if ( count($users) == 0 ) {
		header('Location: ' . get_base_url() . 'newuser.php');
	}
	else {
		header('Location: ' . get_base_url() . 'users.php');
	}

	exit;
}

if ( isset($_POST["username"]) ) {

	$hash = $_POST["hash"];

	if (isset($_POST["pass1"]) && $_POST["pass1"] != "" &&
				$_POST["pass1"] == $_POST["pass2"] ) {
		$hash = hashpass($username, $_POST["pass1"]);
	}
	
	// if the user has changed their username, we need to do a special update
	$oldname = trim(mb_strtolower( $_POST["oldname"] ));
	if ( $oldname != $username ) {
		$store->renameUser($oldname, $username);	
	}

	$store->updateUser($username, $hash, $_POST["email"], isset($_POST["admin"]), false);
	header('Location: ' . get_base_url() . 'users.php');
	exit;
}


global $store;
$users = $store->getAllUsers();
$this_user = $users[$username];

bm_header();
?>
<div class="wrap">


<div class="page_name">
   <h2><?php

if (is_admin()) {
	echo "Edit User";
} else {
	echo "Change Password";
}

?></h2>
</div>

<br/>

<form action="user_edit.php" method="post" name="newuser" accept-charset="utf-8, iso-8859-1">
	<input type="hidden" name="hash" value="<?php echo $this_user["Hash"]; ?>" class="hidden" />

<?php
if (is_admin()) {
?>

	<div class="login_field"><div class="the_legend">Name/Alias:<br/></div>
	<input type="hidden" class="hidden" name="oldname" value="<?php echo $this_user["Name"]; ?>" />
	<input type="text" size="20" name="username" value="<?php echo $this_user["Name"]; ?>" /></div>
	<div class="the_legend">WARNING: Changing the user's name will reset their password - they will need to use
		the 'forgot password' page to get a new one.</div>

	<div class="login_field"><div class="the_legend">Email:<br/></div>
	<input type="text" size="20" name="email" value="<?php echo $this_user["Email"]; ?>" /></div>

<?php
} 

else {
?>
	<input type="hidden" class="hidden" name="oldname" value="<?php echo $this_user["Name"]; ?>" />
	<input type="hidden" class="hidden" name="username" value="<?php echo $this_user["Name"]; ?>" />
	<input type="hidden" class="hidden" name="email" value="<?php echo $this_user["Email"]; ?>" />
<?php
}

if ($is_mine) {

?>

	<div class="login_field"><div class="the_legend">Password:<br/></div>
	<input type="password" size="20" name="pass1"/></div>
	<div class="login_field"><div class="the_legend">Password Again:<br/></div>
	<input type="password" size="20" name="pass2"/></div>

<?php
}

if (is_admin()) {
?>

	<input type="checkbox" name="admin" value="1" <?php if ($this_user["IsAdmin"]) { echo " checked"; } ?> /> Make Admin<br/>

<?php
} 
else {
?>
	<input type="hidden" class="hidden" name="admin" value=""/>

<?php
}
?>

<br />
<div class="login_field">
<input type="submit" name="submit" id="submit" value="Update >>"  />
</div>

</form>
</div>

<?php
bm_footer();
?>