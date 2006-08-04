<?php
/**
 * channel editing page
 * @package BroadcastMachine
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
  $store->saveChannel($channel);
}

if ( $do_update ) {
  makeChannelRss($_GET["i"]);
  //header('Location: ' . get_base_url() . "channels.php" );
}

$files = $store->getAllFiles();

bm_header();
?>

<div class="wrap">

<div class="page_name">
   <h2><?php echo $channel['Name']; ?>: Edit Front Page</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/channel_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

A channel's front page is what users will see on the website for the channel.  For each channel, you can choose to feature certain files from your channel and control the appearance of this page.<Br />

<strong><a href="<?php echo $channel['LibraryURL']; ?>">View the <?php echo $channel['Name']; ?> Front Page >></a></strong>

<br />
<br />

<div id="edit_library_settings">
<div class="section_header">Sections on the Front Page</div>
<p><em>You can create special sections that feature certain videos (perhaps the best or most important ones).  Click on a section name below to pick which files will appear in that section.  If the section has no videos selected, it won't appear on the front page.</em></p>

<?php

foreach($channel['Sections'] as $section) {

	print("<div class=\"sect_list\"><a href=\"edit_channel.php?i=" . $_GET['i'] . "&s=" . urlencode($section['Name'])  . "\">"  . $section['Name'] . "</a> <div class=\"action_link\"><a href=\"edit_channel.php?i=" . $_GET["i"] . "&d=1&s=" . urlencode($section['Name']) . "\">(delete)</a></div></div>");

}

?>

<div class="sect_list">
<form method="post" action="edit_channel.php?i=<?php echo $_GET["i"]; ?>" accept-charset="utf-8">
<!-- , iso-8859-1 -->
<input type="text" name="post_section" size="20" value="" /> <input type="submit" value="Add Section" border="0" />
</form>
</div>

<br />


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
	accept-charset="utf-8">
<!-- , iso-8859-1 -->

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