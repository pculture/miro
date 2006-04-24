<?php
/**
 * login/logout page
 *
 * this page handles display the login form, and then calling the right functions to
 * log the user in.  it also handles logging the user out, checking to make sure they
 * have been authorized, etc.
 * @package Broadcast Machine
 */

require_once("include.php");

if (isset($_GET['logout'])) {
  logout();
  header('Location: ' . get_base_url() . 'index.php');
  exit;
}
else if (isset($_GET['hash'])) {

  $newuser = 0;
  $hashlink = $_GET['hash'];
  $username = trim(mb_strtolower( $_GET['username'] ));

  global $store;
  if ($store->authNewUser($hashlink,$username)) {
    $newuser = 1;
    $msg = "You are now registered and may login";
  }
  
}
else {

  $username = (isset($_POST['username'])) ? mb_strtolower($_POST['username']) : '';
  $password = (isset($_POST['password'])) ? $_POST['password'] : '';
  $do_http_auth = (isset($_GET["httpauth"])) ? $_GET["httpauth"] : 0;
  $login = 0;

  if ( $username != '' && $password != '' && login($username, $password, $msg) ) {
    $login = 1;
  } 
  else if ( $do_http_auth && ( isset($_SESSION['user']) || do_http_auth() ) ) {
    $login = 1;
  }
  
  if ( $login == 1 ) {
    if ( is_admin() ) {
      header('Location: ' . get_base_url() . 'admin.php');
    } 
    else {
      header('Location: ' . get_base_url() . 'index.php');
    }
    exit;
  }
  else {
    if ( $username != '' && $password != '' ) {
      $msg = "Unable to log in";
    }
    else {
      $msg = "";		
    }
  }
}

bm_header();
?>



<div class="wrap">
<div class="login_box">

<div class="page_name">
   <h2>Login</h2>
</div>

<?php
	if ($msg != '') {
		print("<p class=\"error\">" . $msg . "</p>");
	}
?>

<form action="login.php" method="post" accept-charset="utf-8, iso-8859-1">
<div class="login_field">
<div class="login_label">Alias:</div> 
<input type="text" size="20" tabindex="1" name="username" value="<?php echo $username; ?>" />
</div>
<div class="login_field">
<div class="login_label">Password:</div> 
<input type="password" name="password" value="" size="20" tabindex="2" />
</div>

<div class="spacer">&nbsp;</div>
<p class="submit">
	<input type="submit" name="submit" id="submit" value="Login >>"  />
</p>
</form>

<div class="login_links">

<?php
global $can_use_cookies;
if ( $can_use_cookies == false ) {
?>
<a href="<?php echo $_SERVER['PHP_SELF']; ?>">Try again</a> | 
<?php
}

// cjm - don't print this link unless we allow registration in the first place
if ( $settings['AllowRegistration'] || is_admin() || count( $store->getAllUsers() ) <= 0 ) {
?>
<a href="newuser.php?f=1">Make a New Account</a> | 
<?php
}
?>

<a href="forgot.php?f=1">Forgot My Password</a>



</div>
</div> <!-- close login_box -->
</div> <!-- close wrap -->



<?php
	bm_footer();
?>