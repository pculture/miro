<?php
/**
 * channel editing page
 * @package Broadcast Machine
 */


require_once("include.php");

if (!is_admin()) {
	header('Location: ' . get_base_url() . 'admin.php');
	exit;
}

$channel = $store->getChannel($_GET["i"]);

if ( !isset($channel) ) {
	die("Couldn't find channel");
}

// delete a section for this channel
if (isset($_GET['d'])) {

	unset($channel['Sections'][$_GET["s"]]);
	unset($_GET['s']);

//	$channels[$_GET["i"]] = $channel;
	$store->saveChannel($channel);
}

$do_update = false;

if (isset($_POST['file_array'])) {

	$do_update = true;

	$file_array = explode(" ", $_POST['file_array']);

	$section = $channel['Sections'][$_GET["s"]];
	$section['Files'] = array();

	foreach ($file_array as $file) {
		$section['Files'][] = $file;
	}

	$channel['Sections'][$_GET["s"]] = $section;

	$store->saveChannel($channel);
}

if (isset($_POST['post_section'])) {

	$do_update = true;

	$sections = $channel['Sections'];
	$sections[$_POST['post_section']]['Name'] = $_POST['post_section'];
	$sections[$_POST['post_section']]['Files'] = array();

	$channel['Sections'] = $sections;
//	$channels[$_GET["i"]] = $channel;

	$store->saveChannel($channel);
}



if (isset($_POST['post_options'])) {

	$do_update = true;

	$channel['Options'] = array();
	$channel['Options']['Thumbnail'] = isset($_POST['post_thumb']);
	$channel['Options']['Title'] = isset($_POST['post_title']);
	$channel['Options']['Creator'] = isset($_POST['post_creator']);
	$channel['Options']['Description'] = isset($_POST['post_desc']);
	$channel['Options']['Length'] = isset($_POST['post_length']);
	$channel['Options']['Filesize'] = isset($_POST['post_filesize']);
	$channel['Options']['Published'] = isset($_POST['post_published']);
	$channel['Options']['Torrent'] = isset($_POST['post_torrent']);
	$channel['Options']['URL'] = isset($_POST['post_url']);
	$channel['Options']['Keywords'] = isset($_POST['post_keywords']);

	$css = $_POST['post_css'];

	if ($css == "") {
		$css = $_POST['post_css_custom'];
	}

	if ($css == "") {
		$css = "default.css";
	}

	$channel['CSSURL'] = $css;
	
	$store->saveChannel($channel);
}

if ( $do_update ) {
	makeChannelRss($_GET["i"]);
 	header('Location: ' . get_base_url() . "channels.php" );
}


$files = $store->getAllFiles();

bm_header();
?>

<div class="wrap">

<div class="page_name">
   <h2><?php echo $channel['Name']; ?>: Edit Library Display</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channel_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

A channel's library view is what gets displayed on the website for the channel.  This page lets you feature certain files from your channel and control the appearance of the library page.<Br />

<strong><a href="<?php echo $channel['LibraryURL']; ?>">>> View the <?php echo $channel['Name']; ?> Library >></a></strong>

<br />
<br />

<div id="edit_library_settings">
<div class="section_header">Sections on the Front Page</div>
<p><em>Click a section name to pick which files it will display.</em></p>

<?php

foreach($channel['Sections'] as $section) {

	print("<div class=\"sect_list\"><a href=\"edit_channel.php?i=" . $_GET['i'] . "&s=" . urlencode($section['Name'])  . "\">"  . $section['Name'] . "</a> <div class=\"action_link\"><a href=\"edit_channel.php?i=" . $_GET["i"] . "&d=1&s=" . urlencode($section['Name']) . "\">(delete)</a></div></div>");

}

?>

<div class="sect_list">
<form method="post" action="edit_channel.php?i=<?php echo $_GET["i"]; ?>" accept-charset="utf-8, iso-8859-1">
<input type="text" name="post_section" size="20" value="" /> <input type="submit" value="Add Section" border="0" />
</form>
</div>

<br />

<div class="section_header">Display Options</div>

<form method="post" action="edit_channel.php?i=<?php echo $_GET["i"]; ?>" name="display_options" accept-charset="utf-8, iso-8859-1">
<input type="hidden" name="post_options" value="1" class="hidden"/>

<p><em>Select attributes to show for each file. Applies to all sections.</em></p>
<ul style="edit_library_options">
<li><input type="checkbox" name="post_thumb"<?php if ($channel['Options']['Thumbnail']) print(" checked=\"true\""); ?>>Thumbnail</li>
<li><input type="checkbox" name="post_title"<?php if ($channel['Options']['Title']) print(" checked=\"true\""); ?>>Title</li>
<li><input type="checkbox" name="post_creator"<?php if ($channel['Options']['Creator']) print(" checked=\"true\""); ?>>Creator's Name</li>
<li><input type="checkbox" name="post_desc"<?php if ($channel['Options']['Description']) print(" checked=\"true\""); ?>>Description</li>
<li><input type="checkbox" name="post_length"<?php if ($channel['Options']['Length']) print(" checked=\"true\""); ?>>Play Length</li>
<li><input type="checkbox" name="post_filesize"<?php if ($channel['Options']['Filesize']) print(" checked=\"true\""); ?>>File Size</li>
<li><input type="checkbox" name="post_published"<?php if ($channel['Options']['Published']) print(" checked=\"true\""); ?>>Published Date</li>
<li><input type="checkbox" name="post_torrent"<?php if ($channel['Options']['Torrent']) print(" checked=\"true\""); ?>>Torrent Stats</li>
<li><input type="checkbox" name="post_url"<?php if ($channel['Options']['URL']) print(" checked=\"true\""); ?>>Associated URL</li>
</ul>
<br />

<div class="section_header">Visual Theme</div>
<p><em>Select a style for your library page.</em></p>

<ul style="edit_library_options">
Visual Theme:<br/>

<li><input type="radio" name="post_css" value="default.css"<?php if ($channel['CSSURL'] == "default.css") print(" checked=\"true\""); ?>> Default</li>
<li><input type="radio" name="post_css" value=""<?php if ($channel['CSSURL'] != "default.css") print(" checked=\"true\""); ?>> Custom CSS file.  Enter URL: <br />&nbsp;&nbsp;&nbsp;&nbsp;<input type="text" size="22" name="post_css_custom" onFocus="document.display_options.post_css[1].checked = true;" value="<?php if ($channel['CSSURL'] != "default.css") echo $channel['CSSURL']; ?>" /></li>
</ul>
<br />

<div class="section_header">Other Settings</div>
<ul>
<li><input type="checkbox" name="post_keywords"<?php if ($channel['Options']['Keywords'] == "1") print(" checked=\"true\""); ?>> Display Tags list in sidebar.</li>
</ul>

<p class="publish_button" style="clear: both;">
<input type="submit" value="Save Changes" border=0 />
</p>

</form>
</div> <!-- close library settings -->

<?php
if (isset($_GET['s'])) {
?>

<script language="javascript">
function section_manage(frm) {

	frm.file_array.value = '';

	for( i = 0; i < frm.files.length; i++ ) {

		if (frm.files[i].checked) {
			if (frm.file_array.value != '') {
				frm.file_array.value += ' ';
			}
			frm.file_array.value += frm.files[i].value;
		}
	}

	return true;
}
</script>

<form 
	method="post" 
	action="edit_channel.php?i=<?php echo $_GET["i"]; ?>&s=<?php echo urlencode($_GET['s']); ?>" 
	onSubmit="return section_manage(this);"
	accept-charset="utf-8, iso-8859-1">

<input type="hidden" name="file_array" value="" class="hidden">
<input type="submit" value="Save Changes" class="hidden">
<input type="hidden" name="files" value="" class="hidden">

<div id="edit_library_list">
<div style="background-color: #FFFFD1;" padding: 5px;>
<strong>NOW EDITING: <?php echo strtoupper($_GET['s']); ?></strong>
</div>

<p><em>Check off the files to display in this section.</em></p>

<div class="library_check_list">
<p class="publish_button" style="clear: both;">
<input type="submit" value="Save Changes" border=0 />
</p>
</div>

<?php
foreach ($channel['Files'] as $file) {

	if (isset($files[$file[0]])) {
		$data = $files[$file[0]];
?>

		<div class="library_check_list">
		<div class="check_box">

		<input type="checkbox" name="files" value="<?php

			print($file[0] . '" ');

			foreach ($channel['Sections'][$_GET['s']]['Files'] as $fileID) {

				if ($fileID == $file[0]) {

					print(" checked=\"true\"");

					break;

				}

			}
		?>>
		</div>

		<div class="library_video_display">
			 <div class="video_logo"><?php
				if ($data["Image"] != '') {
					print("<img src=\"" . $data["Image"] . "\" width=65/>");
				} else {
					print("<img src=\"t.gif\" width=65/>");
				}
			?></div>

			 <div class="video_name"><?php echo $data['Title']; ?></div>
			 <div class="video_description"><?php echo mb_substr($data["Description"],0,50); ?></div>

		</div>
		</div>

		<div style="clear: both; font-size: 2px; height: 2px;">&nbsp;</div>
<?php

	}

}
?>

<div class="library_check_list">
<p class="publish_button" style="clear: both;">
<input type="submit" value="Save Changes" border=0 />
</p>
</div>

</div> <!-- close edit library list -->
</form>

<div style="clear: both; font-size: 2px; height: 2px;">&nbsp;</div>
</div>

<?php
}

bm_footer();
?>