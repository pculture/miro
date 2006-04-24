<?php
/**
 * donation setup creation/edit page
 * @package Broadcast Machine
 */
require_once("include.php");

if ( ! is_admin() ) {
	header("Location: " . get_base_url() . "index.php");
}

global $store;
global $settings;
global $perm_level;

//
// code to delete a donation setup
//
if ( isset($_GET["id"]) && isset($_GET["action"]) && $_GET["action"] == "delete" ) {
	$store->deleteDonation($_GET["id"]);
	header('Location: ' . get_base_url() . "donations.php" . "");
	exit;
}

if (isset($_POST['donation_text'])) {

	$donations = 	$store->getAllDonations();

	// we don't encode this because the user can enter in html if they want, but we will do
	// some formatting on display, and we'll make sure it's UTF-8 happy for now
	$donation_text = $_POST['donation_text'];
	if ( isset($_POST['donation_email']) ) {
		$donation_email = encode($_POST['donation_email']);
	}
	$donation_title = encode($_POST['donation_title']);

	if ( ! isset($_POST['id']) || $_POST['id'] == "" ) {
		$donationhash = md5( microtime() . rand() );
		while ( isset($donations[$donationhash]) ) {
			$donationhash = md5( microtime() . rand() );		
		}
	}
	else {
		$donationhash = $_POST["id"];
	}

	$donation["text"] = $donation_text;	
	if ( isset($donation_email) ) {
		$donation["email"] = $donation_email;	
	}
	else {
		unset($donation["email"]);
	}
	$donation["title"] = $donation_title;	
	$store->saveDonation($donation, $donationhash);
	
	//
	// update the feeds containing any files that are using this donation text
	//
	$files = $store->getAllFiles();
	$channels = $store->getAllChannels();
	$donations = 	$store->getAllDonations();

	$update_channels = array();

	if ( isset($donations[$donationhash]['Files']) ) {
		foreach( $donations[$donationhash]['Files'] as $hash => $val ) {
			foreach ( $channels as $channel ) {
				if ( $store->channelContainsFile($hash, $channel) ) {
					if ( !isset($update_channels[$channel['ID']]) ) {
						$update_channels[$channel['ID']] = $channel['ID'];
					}
				}
			}
		}
	}
		
	foreach($update_channels as $c) {
		makeChannelRss($c, false);
	}

	header('Location: ' . get_base_url() . "donations.php");
	exit;
}


if (isset($_GET["id"])) {
	$donations = 	$store->getAllDonations();
	$id = $_GET["id"];
	$donation_text = $donations[$_GET["id"]]["text"];
	$donation_email = $donations[$_GET["id"]]["email"];
	$donation_title = $donations[$_GET["id"]]["title"];
} 
else {
	$donation_text = "";
	$donation_email = "";
	$donation_title = "";
}

bm_header();

?>


<div class="wrap">

<form method="post" action="donation.php" id="post" name="post" enctype="multipart/form-data" accept-charset="utf-8, iso-8859-1" onSubmit="return do_submit(this);">
<input type="hidden" name="id" value="<?php if ( isset($id) ) echo $id; ?>" class="hidden"/>

<div id="poststuff">
<div class="page_name">
   <h2>Create a New 'Donation' Setup</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channel_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

<div class="section">

<p>
This string of html will appear as a video plays inside DTV and it can be anything you'd 
like (not just donation requests).  You can use this space to ask for donations or to promote 
your website, DVD, t-shirts, mailing list, etc.  You can also use it to get feedback from your 
viewers: provide a link to a site where they can comment on a video, for example.
</p>

<fieldset>
<div class="the_legend">Title: </div><br />
<input type="text" name="donation_title" size="40" value="<?php if ( isset($donation_title) ) echo $donation_title; ?>" />
</fieldset>

<fieldset>
<div class="the_legend">Enter HTML Here: </div><br />
<textarea name="donation_text" rows="4" cols="80">
<?php if ( isset($donation_text) ) echo $donation_text; ?>
</textarea>
</fieldset>

<p>
<strong>Note:</strong> only the first 100-150 characters will fit on the screen while the video plays, so be succinct.
</p>


<p><strong>Create a paypal donate link.</strong>  Enter your paypal email address below and click 
'make donation link' to generate a link that will allow people to directly donate 
to you using paypal.
</p>

<!--
create a donation setup just means giving people space to make an arbitrary string of html 
(see below).  but we also want to help them make a link to their paypal account.  i believe 
that this link format will link to donate for anyone if they replace my email address with
theirs:

https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business=npr%
40fujichia%
2ecom&item_name=Donation&no_shipping=0&no_note=1&tax=0&currency_code=USD
&charset=UTF%2d8&charset=UTF%2d8

Can we make a little javascript thing that you paste in an email and click 
'generate paypal link' and it pops this link into the field that we provide 
for the html string?

-->
<SCRIPT LANGUAGE="JavaScript">
function generate_paypal() {
	frm = document.getElementById('post');
	email = frm.donation_email.value;

	if ( email != '' ) {	
		output = 'https://www.paypal.com/cgi-bin/webscr?';
		output = output + 'cmd=_xclick&amp;item_name=Donation&amp;no_shipping=0&amp;no_note=1&amp;tax=0&amp;currency_code=USD&amp;charset=UTF%2d8&amp;';
		output = output + 'business=' + email;
	
		frm.donation_text.value = frm.donation_text.value + '\n<a href="' + output + '">Donate</a>';
	}
	else {
		alert("Please enter an email address");
	}
}

function do_submit(frm) {

	var err = '';

	if ( frm.donation_title.value == ''  ) {
		err = 'Please enter a title for this donation setup.';
	}

	if ( frm.donation_text.value == ''  ) {
		err = 'Please enter some text for this donation setup.';
	}

	if (err == '') {
		return true;
	} 

	alert(err);
	return false;
}
</script>

<fieldset>
<div class="the_legend">PayPal Email Address: </div> 
<input type="text" name="donation_email" size="30" value="<?php echo $donation_email; ?>" /> <a onclick="javascript:generate_paypal();">Make Donation Link</a>
</fieldset>

<br />
<input type="submit" value="SAVE DONATION SETUP" />

</div>
</div>
</div>

</form>

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
