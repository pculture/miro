<?php
/**
 * Channel creation page
 * @package Broadcast Machine
 */

require_once("include.php");

if ( ! is_admin() ) {
	header("Location: " . get_base_url() . "index.php");
	exit;
}

global $settings;
global $perm_level;


if (isset($_POST['post_title'])) {

	if ( isset($_POST['post_image']) ) {
		$icon = $_POST['post_image'];
	}
	else {
		$icon = "";
	}

	if (isset($_FILES["post_image_upload"])) {

		if (!file_exists('thumbnails')) {
			mkdir("thumbnails",$perm_level);
		}

		if (move_uploaded_file($_FILES['post_image_upload']['tmp_name'], "thumbnails/" . $_FILES['post_image_upload']['name'])) {
			chmod("thumbnails/" . $_FILES['post_image_upload']['name'], 0644);
			$icon = get_base_url() . "thumbnails/" . $_FILES['post_image_upload']['name'];
		}
	}

	if ( isset($_POST['post_use_auto']) && $_POST['post_use_auto'] == '1') {
//		$url = "";
	} 
	else if ( isset($_POST['post_homepage']) ) {
		$url = $_POST['post_homepage'];
	}

//	if( isset($_POST["post_id"]) && $_POST["post_id"] != "" ) {

	if( isset($_POST["post_id"]) && $_POST["post_id"] != "" ) {
		$channel = $store->getChannel($_POST["post_id"]);
	}
	else {
		$channel = array();
		$channel["Files"] = array();
	}


		if ($icon == "http://") {
			$icon = "";
		}

		$channel["Name"] = encode($_POST['post_title']);
		$channel["Description"] = encode($_POST['post_description']);
		
		if ( isset($url) ) {
			$channel["LibraryURL"] = $url;
		}
		$channel["Icon"] = $icon;
		if ( isset($_POST['post_publisher']) ) {
			$channel["Publisher"] = encode($_POST['post_publisher']);
		}
		$channel["OpenPublish"] = isset($_POST['post_open']);
		$channel["RequireLogin"] = isset($_POST['RequireLogin']);
		$channel["NotPublic"] = isset($_POST['NotPublic']);

		$store->saveChannel($channel);

		if (file_exists("publish/" . $_POST["post_id"] . ".rss")) {
			unlink_file("publish/" . $_POST["post_id"] . ".rss");
		}
/*
	} 
	else {

		$store->addNewChannel( 
			encode($_POST['post_title']),
			encode($_POST['post_description']),
			isset($_POST['post_image']) ? $_POST['post_image'] : '',
			isset($_POST['post_publisher']) ? $_POST['post_publisher'] : '',
			$url, '', '', '',
			isset($_POST['post_open']) );

	}*/

	if (isset($_POST['post_open'])) {
		$settings['HasOpenChannels'] = true;
		$store->saveSettings($settings);
	}

	header('Location: ' . get_base_url() . "channels.php" . "");
	exit;
}


if (isset($_GET["i"])) {

//	$channels = $store->getAllChannels();
//	$channel = $channels[$_GET["i"]];
	$channel = $store->getChannel($_GET["i"]);
	
	if ( !isset($channel) ) {
		die("Couldn't find channel");
	}
	
	$name = isset($channel["Name"]) ? $channel["Name"] : '';
	$desc = isset($channel["Description"]) ? $channel["Description"] : '';
	$icon = isset($channel["Icon"]) ? $channel["Icon"] : '';
	$publisher = isset($channel["Publisher"]) ? $channel["Publisher"] : '';
	$open = isset($channel["OpenPublish"]) ? $channel["OpenPublish"] : '';
	$url = isset($channel["LibraryURL"]) ? $channel["LibraryURL"] : '';
	
	// cjm - this was only an isset before, so even if RequireLogin was set to false,
	// the checkbox was activated
	$RequireLogin = isset($channel["RequireLogin"]) && $channel["RequireLogin"] == true;

	$NotPublic = isset($channel["NotPublic"]) && $channel["NotPublic"] == true;

	if (stristr($url,get_base_url())) {
		$url = '';
	}

	$id = $_GET["i"];
} 
else {
	$name = '';
	$desc = '';
	$icon = '';
	$publisher = '';
	$open = false;
	$url = '';
	$id = '';
	$RequireLogin = false;
	$NotPublic = false;
}



bm_header();

?>


<div class="wrap">

<form method="post" action="create_channel.php" name="post" enctype="multipart/form-data" accept-charset="utf-8, iso-8859-1">
<input type="hidden" name="post_id" value="<?php echo $id; ?>" class="hidden"/>
<div id="poststuff">
<div class="page_name">
   <h2>Create / Edit a Channel</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channel_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

<div class="section">
<fieldset>
<div class="the_legend">Channel Name: </div><br /><input type="text" name="post_title" size="38" value="<?php echo $name; ?>" />
</fieldset>

<fieldset>
   <div class="the_legend">Description:</div><br />
   <textarea rows="4" cols="40" name="post_description" id="content"><?php echo $desc; ?></textarea>
</fieldset>


<fieldset><div class="the_legend">Channel Icon: </div>

<a href="#" onClick="document.getElementById('specify_image').style.display = 'none'; document.getElementById('upload_image').style.display = 'block'; return false;">Upload Image</a> or <a href="#" onClick="document.getElementById('upload_image').style.display = 'none'; document.getElementById('specify_image').style.display = 'block'; return false;">Specify URL</a>

<div style="display:none;" id="upload_image">
<input type="file" name="post_image_upload" value="Choose File" />
</div>

<div id="specify_image" style="display:<?php

if ($icon == "" || $icon == "http://") {
	echo "none";
} 
else {
	echo "block";
}
?>;" >

<input type="text" name="post_image" size="38" value="<?php echo $icon; ?>"/>
</div>
</fieldset>

<fieldset><div class="the_legend">Allow Non-admins to Post: </div><input type="checkbox" name="post_open" <?php
if ($open) {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset><div class="the_legend">Require Users to Login to View: </div><input type="checkbox" name="RequireLogin" <?php
if ($RequireLogin) {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset><div class="the_legend">Hide Channel From Public: </div>
<input type="checkbox" name="NotPublic" <?php
if ($NotPublic) {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset>
<div class="the_legend">Publisher (optional): </div><br /><input type="text" name="post_publisher" size="38" value="<?php echo $publisher; ?>" id="title" />
</fieldset>

<fieldset>
<div class="the_legend">Channel Homepage (optional): </div><br /><input type="radio" name="post_use_auto" value="1" <?php
if ($url == '') {
	echo " checked=\"true\"";
}
?>>Use Automatic Library or

<input type="radio" name="post_use_auto" value="0" <?php

if ($url != '') {
	echo " checked=\"true\"";
}
?>>Use Custom Library at <input type="text" name="post_homepage" size="38" value="<?php echo $url; ?>" id="title" onFocus="document.post.post_use_auto[1].checked = true;"/>
</fieldset>

<p class="publish_button" style="clear: both;">
<input style="border: 1px solid black;" type="submit" value="<?php
if (isset($_GET["i"])) {
	echo "&gt;&gt; Edit Channel";
} 
else {
	echo "&gt;&gt; Create Channel";
}
?>" border=0 alt="Continue" />

</p>

</div>
</div>
</div>

</form>

<?php
bm_footer();
?>
