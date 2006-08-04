<?php
/**
 * donations setup page
 * @package BroadcastMachine
 */


require_once("include.php");

if (!is_admin()) {
	header('Location: ' . get_base_url() . 'admin.php');
	exit;
}

	$donations = $store->getAllDonations();
	bm_header();
?>


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

<div class="wrap">
<div class="page_name">
   <h2>Donation Setups</h2>
<!--
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channels_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
-->
</div>


<?php
if ( is_array($donations) ) {
	foreach($donations as $id => $donation) {
		if ( isset($donation["title"]) && isset($donation["text"]) ) {
?>

<div class="donation_setup">
<div class="donation_preview">
 <div class="setup_title">
 		<span class="setup_nickname"><?php echo $donation["title"]; ?></span>
  	<div class="edit_donation">
		 	<a href="donation.php?id=<?php echo $id; ?>">Edit Setup</a>
		 	<a href="donation.php?id=<?php echo $id; ?>&amp;action=delete" onClick="return confirm('Are you sure you want to delete this donation setup?');">Delete</a>
		</div>
 </div>

<div class="donation_content">
<div class="preview_label">PREVIEW:</div> 
<?php echo $donation["text"]; ?>
</div>
</div>
  <div class="donation_stats">
Linked to <?php if ( isset($donation['Files']) ) echo count($donation['Files']); else echo "0"; ?> files.</a>
 </div>
</div>

<?php
		} // if
	} // foreach
} // if (is array)
?>

<br /><br />
<strong><a href="donation.php">NEW DONATION SETUP</a></strong>


<?php
bm_footer();
?>