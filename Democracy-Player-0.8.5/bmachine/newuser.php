<?php
/**
 * user creation page
 *
 * users access this page to create their account
 * @package BroadcastMachine
 */

global $NEW_USER;
$NEW_USER = 1;

require_once("include.php");


$is_front = false;

if (isset($_GET["f"]) || isset($_POST["f"])) {
  $is_front = false;
}

global $store;
$users = $store->getAllUsers();

if ( count($users) > 0 ) {
	
  global $settings;

  if ( ! is_admin() && 
       (!isset($settings['AllowRegistration']) || 
	$settings['AllowRegistration'] == 0 || 
	$settings['AllowRegistration'] == "" ) ) {
    
    front_header("Access Denied");
    print("Sorry, new user registration isn't allowed");
    front_footer();
    exit;
    
  }
}


global $settings;
$email = (isset($_POST['email'])) ? $_POST['email'] : '';
$username = (isset($_POST['username'])) ? $_POST['username'] : '';
$username = encode(trim(mb_strtolower( $username )));

$pass1 = (isset($_POST['pass1'])) ? $_POST['pass1'] : '';
$pass2 = (isset($_POST['pass2'])) ? $_POST['pass2'] : '';

$msg = "";

$show_form = true;

if ( strlen($email) > 0 && strlen($username) > 0 && 
     strlen($pass1) > 0 && $pass1 == $pass2 ) {


  global $store;
  if ( $store->addNewUser($username, $pass1, $email, false, $is_front, $error) ) {

    $show_form = false;
	
    $msg = "The account $username was added successfully. <a href='admin.php'>Continue</a>";

    $users = $store->getAllUsers();
		
    // if this is the fist user who has registered, validate them automatically
    if ( $settings['RequireRegAuth'] == true && count($users) > 0 ) {
      $msg .= "<br/><br/>You should receive an email verifying your account. 
        Follow the instructions in that email to continue the authentication process";
    }
    else {
      $hashlink = $store->userHash( $username, $pass1, $email );
      $result = $store->authNewUser( $hashlink, $username );
      
      if ( $result == true ) {
	login( $username, $pass1, $error );
      }
      else {
	global $errstr;
	$msg = "Auth Error: $errstr";
      }
    }
    
  } 
  else {
    // if we get here, there was a filesystem error or something like that
    $msg = "Your account could not be added. <strong>" . $error . "</strong>";
  }
}
else if ( isset($_POST["do_login"]) ) {
  if ( strlen($email) == 0 ) {
    $msg = "<strong>Please specify an email address</strong>";	
  }
  else if ( strlen($username) == 0 ) {
    $msg = "<strong>Please specify a username</strong>";	
  }
  else if ( strlen($pass1) == 0 ) {
    $msg = "<strong>Please enter a password</strong>";	
  }
  else if ( $pass1 != $pass2 ) {
    $msg = "<strong>Your password doesn't match - please enter it again</strong>";	
  }
}


if ($is_front) {
  front_header("New Account");
} 
else {
  bm_header();
}

?>

<div class="wrap">
<div class="signup_box">
<div class="page_name">
   <h2>New Account</h2>
</div>



<?php

if ($msg != "") {
  print("<p class=\"error\">" . $msg . "</p>");
} 
else {
  
  if (isset($_GET["msg"])) {
    print "<p class=\"error\">You are required to register in order to 
						download this file.  Please create an account below.</p>";
  }
  if ( count($users) == 0 ) {
    print "<p class=\"error\">This looks like your first time using Broadcast Machine.  
					You should create a new user account before continuing.</p>
					<p><strong>NOTE:</strong> If you have trouble installing Broadcast Machine, please
					send us an <a href='mailto:colin@jerkvision.com'>email</a> and let us know about it.";
  }
}

if ( $show_form == true ) {
?>

<form action="newuser.php" method="post" accept-charset="utf-8">
<!-- , iso-8859-1 -->
  <input type="hidden" name="do_login" class="hidden" value="1" />
<?php

   if ($is_front) {
?>
  <input type="hidden" class="hidden" name="f" value="1"/>
<?php
   }
?>

<fieldset>
<div class="login_field">
  <div class="login_label">Email: </div><br /><input type="text" size="17" name="email" value="<?php echo htmlspecialchars($email); ?>"  />
</div>
</fieldset>

<fieldset>
<div class="login_field">
  <div class="login_label">Name / Alias: </div><br /><input type="text" size="17" name="username" value="<?php echo htmlspecialchars($username); ?>"  />
</div>

</fieldset>

<fieldset>
<div class="login_field">
  <div class="login_label">Password: </div><br /><input type="password" name="pass1" size="10" value="" />
</div>
</fieldset>

<fieldset>
<div class="login_field">
  <div class="login_label">Password Again: </div><br /><input type="password" name="pass2" size="10" value="" />
</div>
</fieldset>

<div class="spacer">&nbsp;</div>
<p class="submit">
<input style="border: 1px solid black; font-size: 16px;" type="submit" value="Register >>" border=0 alt="&gt;&gt; Continue" />

</p>
</div>
</form>

<?php
}

if ($is_front) {
  front_footer();
} 
else {
  bm_footer();
}
?>

