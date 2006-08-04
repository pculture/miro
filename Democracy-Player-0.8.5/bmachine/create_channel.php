<?php
/**
 * Channel creation page
 * @package BroadcastMachine
 */

require_once("include.php");

if ( ! is_admin() ) {
  header("Location: " . get_base_url() . "index.php");
  exit;
}

global $settings;
global $store;

if (isset($_GET["i"])) {
  $channel = $store->getChannel($_GET["i"]);
}
else if( isset($_POST["ID"]) && $_POST["ID"] != "" ) {
  $channel = $store->getChannel($_POST["ID"]);
} else {
  $channel = $store->newChannel();
}

if (isset($_POST['Name'])) {

  if ( !isset($_POST['Icon']) ) {
    $_POST['Icon'] = "";
  }
  $channel["Icon"] = $_POST["Icon"];

  if (isset($_FILES["IconUpload"]) && $_FILES["IconUpload"]["size"] > 0 ) {
    make_folder($thumbs_dir);
    
    if ( move_uploaded_file($_FILES['IconUpload']['tmp_name'], "$thumbs_dir/" . $_FILES['IconUpload']['name'])) {
      chmod("$thumbs_dir/" . $_FILES['IconUpload']['name'], perms_for(FILE_PERM_LEVEL) );
      $channel["Icon"] = get_base_url() . "$thumbs_dir/" . $_FILES['IconUpload']['name'];
    }
  }
  
  if ( isset($_POST['post_use_auto']) && $_POST['post_use_auto'] == '1') {
    $channel["LibraryURL"] = "";
  }
  else if ( isset($_POST["LibraryURL"]) ) {
    $channel["LibraryURL"] = $_POST["LibraryURL"];
  }

  /* 
  else if ( isset($_POST['LibraryURL']) ) {
    $url = $_POST['LibraryURL'];
  }*/
    

  if ( $channel["Icon"] == "http://" ) {
    $channel["Icon"] = "";
  }

  $channel["Name"] = encode($_POST['Name']);
  $channel["Description"] = encode($_POST['Description']);
  
  if ( isset($_POST['Publisher']) ) {
    $channel["Publisher"] = encode($_POST['Publisher']);
  }
  $channel["OpenPublish"] = isset($_POST['OpenPublish']);
  $channel["RequireLogin"] = isset($_POST["RequireLogin"]);
  $channel["NotPublic"] = isset($_POST["NotPublic"]);

  $channel['Options'] = array();
  $channel['Options']['Thumbnail'] = isset($_POST['Options']['Thumbnail']);
  $channel['Options']['Title'] = isset($_POST['Options']['Name']);
  $channel['Options']['Creator'] = isset($_POST['Options']['Creator']);
  $channel['Options']['Description'] = isset($_POST['Options']['Description']);
  $channel['Options']['Length'] = isset($_POST['Options']['Length']);
  $channel['Options']['Filesize'] = isset($_POST['Options']['Filesize']);
  $channel['Options']['Published'] = isset($_POST['Options']['Published']);
  $channel['Options']['Torrent'] = isset($_POST['Options']['Torrent']);
  $channel['Options']['URL'] = isset($_POST['Options']['post_url']);
  $channel['Options']['Keywords'] = isset($_POST['Options']['Keywords']);

  $subscription_values = 0;

  if ( isset($_POST['SubscribeOptions']) ) {
    foreach( $_POST['SubscribeOptions'] as $o ) {
      $subscription_values |= $o;
    }
  }

  $channel['Options']['SubscribeOptions'] = $subscription_values;
  /*
  $css = $_POST['post_css'];

  if ($css == "") {
    if ( isset($_POST['post_css_custom']) && $_POST['post_css_custom'] != "" ) {
      $css = $_POST['post_css_custom'];
    }
    else {
      $css = "default.css";
    }
  }
  $channel['CSSURL'] = $css;
  */

  $channel['CSSURL'] = "default.css";

  $store->saveChannel($channel);
  makeChannelRss($channel["ID"], true);

  if (isset($_POST['OpenPublish'])) {
    $settings['HasOpenChannels'] = true;
    $store->saveSettings($settings);
  }

  header('Location: ' . get_base_url() . "channels.php" . "");
  exit;
}


/*if (isset($_GET["i"])) {
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
*/

bm_header();

?>


<div class="wrap">

<form method="post" action="create_channel.php" name="post" enctype="multipart/form-data" accept-charset="utf-8">
<!-- , iso-8859-1 -->
<input type="hidden" name="ID" value="<?php echo $channel["ID"]; ?>" class="hidden"/>
<div id="poststuff">
<div class="page_name">
   <h2>Create / Edit a Channel</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channel_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

<div class="section">

<div class="section_header">Channel Info</div>
<fieldset>
<div class="the_legend">Channel Name: </div><br /><input type="text" name="Name" size="38" value="<?php echo $channel["Name"]; ?>" />
</fieldset>

<fieldset>
   <div class="the_legend">Description:</div><br />
   <textarea rows="4" cols="40" name="Description" id="content"><?php echo isset($channel["Description"]) ? $channel["Description"] : ''; ?></textarea>
</fieldset>


<fieldset><div class="the_legend">Channel Icon: </div>

<a href="#" onClick="document.getElementById('specify_image').style.display = 'none'; document.getElementById('upload_image').style.display = 'block'; return false;">Upload Image</a> or <a href="#" onClick="document.getElementById('upload_image').style.display = 'none'; document.getElementById('specify_image').style.display = 'block'; return false;">Specify URL</a>

<div style="display:none;" id="upload_image">
<input type="file" name="IconUpload" value="Choose File" />
</div>

<div id="specify_image" style="display:<?php

if ( !isset($channel["Icon"]) || $channel["Icon"] == "" || $channel["Icon"] == "http://") {
	echo "none";
} 
else {
	echo "block";
}
?>;" >

<input type="text" name="Icon" size="38" value="<?php echo isset($channel["Icon"]) ? $channel["Icon"] : ''; ?>"/>
</div>
</fieldset>

<fieldset><div class="the_legend">Allow Non-admins to Post: </div><input type="checkbox" name="OpenPublish" <?php
if (isset($channel["NotPublic"] ) && $channel["NotPublic"] != false ) {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset><div class="the_legend">Require Users to Login to View: </div><input type="checkbox" name="RequireLogin" <?php
if (isset($channel["RequireLogin"]) && $channel["RequireLogin"] != false )  {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset><div class="the_legend">Hide Channel From Public: </div>
<input type="checkbox" name="NotPublic" <?php
if (isset($channel["NotPublic"] ) && $channel["NotPublic"] != false ) {
	echo " checked=\"true\"";
}
?>/></fieldset>

<fieldset>
<div class="the_legend">Publisher (optional): </div><br />
<input type="text" name="Publisher" size="38" value="<?php echo isset($channel["Publisher"]) ? $channel["Publisher"] : ''; ?>" id="title" />
</fieldset>

<fieldset>
<div class="the_legend">Channel Homepage (optional): </div><br /><input type="radio" name="post_use_auto" value="1" <?php

$library_url = "library.php?i=" . $channel["ID"];
$use_auto = false;

if (  stristr($channel['LibraryURL'], $library_url) ) {
  $use_auto = true;
  $channel["LibraryURL"] = "";
  echo " checked=\"true\"";
}
?>>Use Automatic Library or

<input type="radio" name="post_use_auto" value="0" <?php

if ($use_auto == false) {
  echo " checked=\"true\"";
}
?>> 
Use Custom Library at <input 
  type="text" 
  name="LibraryURL" 
  size="38" value="<?php echo $channel["LibraryURL"]; ?>" id="title" onFocus="document.post.post_use_auto[1].checked = true;"/>
</fieldset>

<div class="section_header">Video Info</div>

<p><em>Select attributes to show for each file. Applies to all sections.</em></p>
<fieldset>
<ul style="edit_library_options">
<li><input type="checkbox" name="Options[Thumbnail]"<?php if ($channel['Options']['Thumbnail']) print(" checked=\"true\""); ?>>Thumbnail</li>
<li><input type="checkbox" name="Options[Name]"<?php if ($channel['Options']['Title']) print(" checked=\"true\""); ?>>Title</li>
<li><input type="checkbox" name="Options[Creator]"<?php if ($channel['Options']['Creator']) print(" checked=\"true\""); ?>>Creator's Name</li>
<li><input type="checkbox" name="Options[Description]"<?php if ($channel['Options']['Description']) print(" checked=\"true\""); ?>>Description</li>
<li><input type="checkbox" name="Options[Length]"<?php if ($channel['Options']['Length']) print(" checked=\"true\""); ?>>Play Length</li>
<li><input type="checkbox" name="Options[Filesize]"<?php if ($channel['Options']['Filesize']) print(" checked=\"true\""); ?>>File Size</li>
<li><input type="checkbox" name="Options[Published]"<?php if ($channel['Options']['Published']) print(" checked=\"true\""); ?>>Published Date</li>
<li><input type="checkbox" name="Options[Torrent]"<?php if ($channel['Options']['Torrent']) print(" checked=\"true\""); ?>>Torrent Stats</li>
<li><input type="checkbox" name="Options[URL]"<?php if ($channel['Options']['URL']) print(" checked=\"true\""); ?>>Associated URL</li>
</ul>
</fieldset>
<br />

<div class="section_header">Other Settings</div>
<fieldset>
<ul>
<li><input type="checkbox" name="Options[Keywords]"<?php if ($channel['Options']['Keywords'] == "1") print(" checked=\"true\""); ?>> Display Tags list.</li>
</ul>
</fieldset>

<div class="section_header">Subscription Links</div>
<p><em>Show subscription links for:</em></p>
<fieldset>
<ul>
<li><input type="checkbox" name="SubscribeOptions[]"<?php if ($channel['Options']['SubscribeOptions'] & 1) print(" checked=\"true\""); ?> value="1"> RSS Feed</li>
<li><input type="checkbox" name="SubscribeOptions[]"<?php if ($channel['Options']['SubscribeOptions'] & 2) print(" checked=\"true\""); ?> value="2"> Democracy</li>
<li><input type="checkbox" 
           name="SubscribeOptions[]"<?php if ($channel['Options']['SubscribeOptions'] & 4) print(" checked=\"true\""); ?> 
           value="4"> iTunes (You must have direct URLs enabled in the <a href="settings.php">settings tab</a> for iTunes compatibility.)</li>
</ul>
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
