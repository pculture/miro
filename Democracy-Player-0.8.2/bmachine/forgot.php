<?php
/**
 * page that handles sending users a link to regenerate their password if
 * they have forgotten it.
 * @package Broadcast Machine
 */

require_once("include.php");

$found = false;

if (isset($_POST["email"])) {
  $email = htmlentities($_POST["email"]);

  global $store;

  $users = $store->getAllUsers();

  $username = "";
  $newpass = "";
	
  foreach ($users as $person) {

    if ($person["Email"] == $email) {
      $username = $person["Name"];
      $found = true;
      break;
    }
  }
  
  if ($found) {
    
    // hash the user's name, password, and a secret key to generate a URL we can send to the user
    $hash = urlencode(base64_encode( $username . "|" . $users[$username]['Hash'] ));
    $url = get_base_url() . "forgot.php?hash=" . $hash;
    
    if ( site_title() != "" ) {
      $title = site_title() . "Broadcast Machine password";
    }
    else {
      $title = "Broadcast Machine password";		
    }
    
    $result = @mail(
		    $email,
		    $title,
		    "Click on this link to reset your password:\n\n$url"
		    );
    
  }
}


if (isset($_POST["username"])) {
  
  if (isset($_POST["pass1"])) {
    
    if (($_POST["pass1"] == $_POST["pass2"]) && $_POST["pass1"] != "") {
      $hash = hashpass($_POST["username"],$_POST["pass1"]);
    }
  }
  
  // grab the user so we can figure out if they are admin or not
  $user = $store->getUser($_POST["username"]);
  
  $store->updateUser($_POST["username"],
		     $hash,
		     $email,
		     isset($user["IsAdmin"]) && $user["IsAdmin"] == 1 ? true : false,
		     isset($user["IsPending"]) && $user["IsPending"] == 1 ? true : false );
  
  login($_POST["username"], $_POST["pass1"], $msg);
  header('Location: ' . get_base_url() . 'admin.php');
  exit;
}

/**
 * user just clicked on the reset link we sent them, 
 * let's allow them to login and change their password.
 */

bm_header();

?>

<div class="wrap">
<div class="login_box">

<div class="page_name">
   <h2>Forgot Password</h2>
</div>

<?php
if ( isset($_GET["hash"]) ) {

	$junk = base64_decode(urldecode($_GET["hash"]));
	$foo = explode("|", $junk);

	$username = $foo[0];
	$hash = $foo[1];

	global $store;
	$users = $store->getAllUsers();

	$this_user = $users[$username];

	if ( ! $this_user || $hash != $this_user['Hash'] ) {
		die("Illegal reset!");
	}

?>

<form action="forgot.php" method="post" name="newuser" accept-charset="utf-8, iso-8859-1">
	<input type="hidden" class="hidden" name="username" value="<?php echo $foo[0]; ?>" />
	<input type="hidden" name="hash" value="<?php echo $this_user["Hash"]; ?>" class="hidden" />
	<input type="hidden" class="hidden" name="username" value="<?php echo $this_user["Name"]; ?>" />
	<input type="hidden" class="hidden" name="email" value="<?php echo $this_user["Email"]; ?>" />
	<input type="hidden" class="hidden" name="admin" value="<?php echo $this_user["admin"]; ?>"/>

	<div class="login_field"><div class="the_legend">Password:<br/></div>
	<input type="password" size="20" name="pass1"/></div>
	<div class="login_field"><div class="the_legend">Password Again:<br/></div>
	<input type="password" size="20" name="pass2"/></div>

<p class="submit">
<input type="submit" name="submit" id="submit" value="Update >>"  />
</p>
</form>

<?php
	exit;
}

if (isset($email)) {
  if ($found) {
    if ( $result == true ) {
?>

<p>Your account information has been sent to <?php echo $email; ?>.</p>
<?php
    }
    else {
?>
	<p>Broadcast Machine can't send mail because of a problem with the mail configuration.  Please contact your server administrator.</p>
<?php		
    }
  } 
  else {
?>
    <p>We were unable to find an account with the email address "<?php echo $email; ?>".  Please <a href="newuser.php">create a new account</a> or enter a different email address below.
<?php

  }
}

if (!$found) {
?>

<form action="forgot.php" method="post" accept-charset="utf-8, iso-8859-1">
<input type="hidden" name="f" value="1" class="hidden"/>

<div class="login_field">
	<div class="login_label">Your Email:</div> 
	<input type="text" size="20" tabindex="1" name="email" value="" />
</div>

<div class="spacer">&nbsp;</div>
<p class="submit">
	<input type="submit" name="submit" id="submit" value="Remind Me >>"  />
</p>
</form>

<?php
}
?>

</div>
</div> <!-- close login_box -->

<?php
  bm_footer();
?>