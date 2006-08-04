<?php
/**
 * file publishing page 
 *
 * this page handles the creation of new files, editing old files, etc.  it has
 * logic to handle torrents, URLs, file uploads, and so on.
 * @package BroadcastMachine
 */
require_once("include.php");
require_once("publishing.php");

//
// don't let the user access this page if they don't have the permission to upload
//
requireUploadAccess();

$channels = $store->getAllChannels();

//
// we need to figure out if this is an admin user, or if it's not,
// is there an accessible channel to post to
//
if ( ! is_admin() ) {

	$has_usable_channel = false;

	foreach ($channels as $channel) {
		if ( $channel["OpenPublish"] ) {
			$has_usable_channel = true;
			break;
		}
	}

	if ( ! $has_usable_channel ) {
		bm_header();
?>
<div class="wrap">
Sorry, there are no publicly accessible channels for publishing content at this time.
</div>
<?php
		bm_footer();
		exit;
	}
}

// http://bitchell.dyndns.org/~colin/bm/publish.php?method=link&Title=foo&post_channels[]=1&post_do_save=1&URL=http://www.nakedrabbit.com/enclosures/mermaid.m4v
// allow for incoming parameters to be specified as part of our URL - should
// make scripting/automating easier for people, and will make generating a
// bookmarklet a lot easier
// see: https://develop.participatoryculture.org/projects/democracy/ticket/1830
// see: https://develop.participatoryculture.org/projects/democracy/ticket/558
$file = array_merge($_GET, $_POST);

if ( isset($file["post_do_save"]) ) {

	set_file_defaults($file);

  debug_message("TRY PUBLISH: " . $file["Title"] );
	$result = publish_file($file);

	if ( $result ) {
    debug_message("TRY PUBLISH: success!");
		session_write_close();
		header('Location: ' . get_base_url() . 'edit_videos.php' );
		exit;
	}


  global $errorstr;
  global $uploaded_file_url;

  if ( (!isset($file["URL"]) || $file["URL"] == "") && isset($uploaded_file_url) ) {
    $file["URL"] = $uploaded_file_url;
    $is_external = 0;
  }
  else if ( isset($uploaded_file_url) && $file["URL"] == $uploaded_file_url ) {
    $is_external = 0;
  }

} // if $_POST["post_do_save"]



bm_header();

if ( isset($_GET["method"]) ) {
	$method = $_GET["method"];
}

if ( isset($method) || isset($_GET["i"]) || isset($_POST["post_do_save"]) ) {
	show_publish_form($file);
}
else {
	pick_publish_method();
}


bm_footer();

function pick_publish_method() {
?>
<div class="wrap">
	<div id="poststuff">

		<div class="page_name">
			 <h2>Publish a File</h2>
			 <div class="help_pop_link">
					<a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/publish_popup.php')">
		<img src="images/help_button.gif" alt="help"/></a>
			 </div>
		</div>

		<div class="section">
			<h3>How would you like to publish this file?</h3>
			
			<p><strong><a href="publish.php?method=upload">Upload the file directly</a></strong><br />Servers sometimes have a limit on 
			the maximum size of an uploaded file. For files larger than 2 or 3 megabytes, we generally recommend either 
			posting a torrent or using an FTP program and then linking to the file. The maximum upload size on this 
			server is <strong><?php echo ini_get("upload_max_filesize"); ?></strong>.</p>
			
			<p><strong><a href="publish.php?method=link">Link to the file</a></strong><br /> Use this option for files that are already on a 
			server. Just enter the link to the file you want to publish.</p>

<script language="JavaScript" type="text/javascript" >
<!--
    isLinux = (navigator.userAgent.indexOf('Windows') <= 0) && (navigator.userAgent.indexOf('Mac') <= 0);

    if ( isLinux ) {
			document.writeln(' \
      <p><strong>Post a torrent</strong><br /> Sorry, this feature only works on Windows and Mac machines.  If you want \
      to post a torrent, you can create the torrent using a BitTorrent application, then upload it as a file.</p>');
    }
    else {
			document.writeln(' \
      <p><strong><a href="publish.php?method=torrent">Post a torrent</a></strong><br /> When you share a file with a torrent, you can reduce \
			or eliminate bandwidth costs. To post a torrent, you first need to have Broadcast Machine Helper. \
      Download it now: \
        <a href="download.php?type=exe">Windows</a> | \
        <a href="download.php?type=mac">Mac</a>. \
			<a target="_blank" href="http://www.getdemocracy.com/broadcast/help/torrent_posting.php">Learn more</a>. </p>');

    }
-->
</script>
<noscript>
      <p><strong>Post a torrent</strong><br />Sorry, the Broadcast Machine Helper only works if you have Javascript 
      enabled.  If you want to post a torrent, you can do so by uploading it or linking to it, otherwise, please turn on
      Javascript in your browser.
</noscript>
		</div>
	</div>
</div>

<?php
}


/********************************************************************************************/
/********************************************************************************************/
/********************************************************************************************/
/********************************************************************************************/

function show_publish_form($file = null) {
	global $store;

	//
	// set up some defaults here
	//
	if ( $file == null ) {
		$file = array();
	}
	set_file_defaults($file);

	if ( isset($_GET["method"]) ) {
		$method = $_GET["method"];
	}

	// there was a problem of some sort
	if ( isset($file["post_do_save"]) ) {
		global $errorstr;
		global $uploaded_file_url;


		if ( (!isset($file["URL"]) || $file["URL"] == "") && isset($uploaded_file_url) ) {
			$file["URL"] = $uploaded_file_url;
			$is_external = 0;
		}		

	} // else

	//
	// user is editing, let's grab the file info
	//
	else if (isset($_GET["i"])) {
		$file = $store->getFile($_GET["i"]);

		if ( !isset($file['SharingEnabled']) ) {
			$file["SharingEnabled"] = false;
		}
	
		$transcript_text = "";
		if (stristr($file["Transcript"], get_base_url())) {
			global $text_dir;
			$transcript_text = file_get_contents("$text_dir/" . $file["ID"] . ".txt");
			$file["Transcript"] = "";
		}
	
    $channels = $store->getAllChannels();	
		foreach ($channels as $channel ) {
			foreach ($channel["Files"] as $list) {
				if ($list[0] == $file["ID"]) {
					$file["post_channels"][] = $channel["ID"];
				}
			}
		}
	
	} 
?>

<SCRIPT LANGUAGE="JavaScript">
<!-- Begin
var hash = '';
var torrent_name = '';
var upload_error = '';

var pollTimer;

function popUp(URL) {
	day = new Date();
	id = day.getTime();

	eval("page" + id + " = window.open(URL, '" + id + "', 'toolbar=0,scrollbars=1,location=0,statusbar=0,menubar=0,resizable=0,width=640,height=600');");

}

function start_polling() {
	if (hash == '') {
		pollTimer = setTimeout('start_polling()', 500);
	} 
	else {
		do_poll();
	}
}

function do_poll() {
	window.frames['poll'].location = 'poll.php?i=' + hash;

	if (torrent_name == "" && upload_error == "" ) {
		pollTimer = setTimeout('do_poll()',5000);
	} 
	else if ( upload_error != "" ) {
		document.getElementById('video_blurb').innerHTML = '<div style="color: #A00;">There was an error in the upload process:<br />' + upload_error + '</div>';
	}
	else {
		document.getElementById('video_blurb').innerHTML = '<div style="color: #A00;">Now sharing "' + torrent_name + '".<br /> <strong>You must keep the BM Helper window open for this file to remain available.</strong></div>';
	}
}


function upload() {
  
    if (hash != '') {
      hash = '';
      torrent_name = '';
    }

    window.frames['uploader'].location = 'trigger.php';
    pollTimer = setTimeout('start_polling()', 500 );
<?php
    // only display this server-sharing checkbox if server sharing is turned on
    global $settings;
    if ( isset($settings["sharing_enable"]) && $settings["sharing_enable"] == 1 ) {
      echo("document.getElementById('server_sharing').style.display = 'block';");
    }
?>

}



function isFull() {

	frm = document.getElementById('post');

	if (document.getElementById('people_table').rows.length > 2) {
		var do_add = true;

		for( i = 0; i < frm.People_name.length; i++ ) {

			if ( frm.People_name[i].value == '' || 
					frm.People_role[i].value == '' ) {
				do_add = false;
				break;
			}
		}

		if (do_add) {
			addPeople();
		}

	} 
	else {

		if (frm.People_name.value != '' && frm.People_role.value != '') {
			addPeople();
		}
	}

}

function clearPeople() {

	// this is the div that holds the table of people
	oDiv = document.getElementById('people_holder');

	// delete the inner table from the div
	oDiv.removeChild(oDiv.firstChild);
	
	// recreate the table
	oDiv.innerHTML = '<table cellpadding="2" cellspacing="0" border="0" id="people_table"><tr><td width="200">&nbsp;</td><td width="200">&nbsp;</td></tr></table>';

	// add the 1st blank back
//	addPeople();
}

function addPeople() {
	addPerson("", "");
}

function addPerson(name, role) {

	lyr = document.getElementById('people_table');

	var oNewRow = lyr.insertRow(-1);
	var oNewCell1 = document.createElement("td");
	var oNewCell2 = document.createElement("td");

	oNewRow.appendChild(oNewCell1);
	oNewRow.appendChild(oNewCell2);

	oNewCell1.innerHTML = '<input type="text" id="person" name="People_name" value="' + name + '" onKeyDown="isFull();"/>';
	oNewCell2.innerHTML = '<input type="text" id="person" name="People_role" value="' + role + '" onKeyDown="isFull();"/>';

}



function do_submit(frm) {

	var err = '';
	if ( hash == '' && frm.ID.value != '' ) {
		hash = frm.ID.value;
	}

	if (hash != '' && (frm.URL.value == '' || frm.URL.value == 'http://') ) {
		frm.URL.value = hash;
		frm.Mimetype.value = 'application/x-bittorrent';
	} 
	
  if (
		(frm.URL.value == '' || frm.URL.value == 'http://') &&
		frm.post_file_upload.value == ''	) {
		err = 'Please enter a file location or upload a file';
	}
	
	if ( frm.Title.value == '' ) {
		err = 'Please enter a title';
	}

	// clear out the values of the form widgets that aren't visible, so their data isn't stored as the file info
/*	if ( document.getElementById('upload_file').style.display == 'block' ) {
		document.getElementById('specify_url').value = '';
		frm.URL.value = '';
		frm.post_use_upload.value = 1;
	}
	else if ( document.getElementById('specify_url').style.display == 'block' ) {
//		document.getElementById('upload_file').value = '';
		frm.post_use_upload.value = 0;
	}
*/

	var channel_count = 0;

  for (i=0; i < document.post.length; i++) {
    if (document.post[i].name == 'post_channels[]') {
      if ( document.post[i].checked == true ) {
      			channel_count++;
      }
    }
  }

	//
	// cjm - ask the user if they want to select a channel before saving
	//	
	if ( channel_count == 0 ) {
		var channel_go = confirm("You haven't selected a channel - Would you like to continue anyway?");
		if ( channel_go == false ) {
			return false;
		}		
	}

	frm.People.value = '';

	if ( document.getElementById('people_table').rows.length > 2 ) {

		for( i=0; i < frm.People_name.length; i++ ) {
			if ( frm.People_name[i].value != '' && frm.People_role[i].value != '' ) {
        //&& trim(frm.People_name[i].value) != '' && trim(frm.People_role[i].value) != '' 
				frm.People.value += frm.People_name[i].value + ':' + frm.People_role[i].value + '\n';
			}
		}

	} 
	else {
    if ( frm.People_name.value != '' && frm.People_role.value != '' ) {
      // && trim(frm.People_name.value) != null && trim(frm.People_role.value) != null
		  frm.People.value = frm.People_name.value + ':' + frm.People_role.value;
	  }
	}

//	frm.post_channel_array.value = channel_array.join(',');

	if (err == '') {

/*		if ( document.getElementById('upload_file').style.display == 'block' ) {
			document.getElementById('progress_bar').style.display = 'block';
			document.getElementById('progress_bar2').style.display = 'block';
		}
*/
		return true;
	} 

	alert(err);
	return false;
}

function submit_force() {
	frm = document.getElementById('post');
	frm.ignore_mime.value = 1;
	if ( do_submit(frm) ) {
		frm.submit();
	}
}

// End -->
</script>


<!-- BASIC PUBLISHING OPTIONS -->
<div class="wrap">
<form name="post" action="publish.php" method="post" id="post" 
		onLoad="this.reset();" onSubmit="return do_submit(this);" enctype="multipart/form-data" 
		accept-charset="utf-8">

	<input type="hidden" name="ignore_mime" class="hidden" value="<?php echo $file['ignore_mime']; ?>" />
	<input type="hidden" name="post_do_save" class="hidden" value="1" />

	<input type="hidden" name="Mimetype" value="<?php echo $file["Mimetype"]; ?>" class="hidden">
	<input type="hidden" name="People" class="hidden" />
	<input type="hidden" name="ID" class="hidden" value="<?php echo $file["ID"]; ?>"/>
<?php
		if ( isset($is_external) ) {
?>
	<input type="hidden" name="is_external" class="hidden" value="<?php echo $is_external; ?>"/>
<?php
		}
?>

<?php
		global $actual_fname;
		if ( isset($actual_fname) ) {
?>
	<input type="hidden" name="actual_fname" class="hidden" value="<?php echo $actual_fname; ?>"/>
<?php
		}
?>

<div id="poststuff">

<div class="page_name">
   <h2>Publish a File</h2>
   <div class="help_pop_link">
      <a href="javascript:popUp('http://www.getdemocracy.com/broadcast/help/publish_popup.php')">
<img src="images/help_button.gif" alt="help"/></a>
   </div>
</div>

<?php 

global $errorstr;
global $do_mime_check;

if ( isset($errorstr) ) {

  if ( $errorstr == "NOFILE" ) {
		$errorstr = "<div id=\"file_errors\"><strong>Error: Sorry, Broadcast Machine doesn't support file:// URLs</strong></div>";
  }
	else if ( $errorstr == "404" ) {
		$errorstr = "<div id=\"file_errors\"><strong>Error: Sorry, it looks like your file isn't at the URL you specified.  <a href='javascript:submit_force();'>Click here</a> to save the file anyway.</strong></div>";
	}
	else if ( $errorstr == "SIZE" ) {
		$errorstr = "<div id=\"file_errors\">
		<strong>Error:</strong> Your file was larger than the maximum allowed size of " . ini_get("upload_max_filesize") . "<br />
		Please try posting the file as a torrent or uploading it manually, then linking to it.		
		</div>";
	}
	else if ( $errorstr == "MIME" && $do_mime_check == true ) {
		$errorstr = build_mime_chooser();
	}

	print $errorstr;
} // if ( error )


if (1 || $file["URL"] == "") {

	if ( $file["URL"] == "" ) {
		$file["URL"] = "http://";
	}
?>

<div class="section">
<fieldset id="video_file">
<?php
if ( isset($method) ) {
	if ( $method == "torrent" ) {
?>
<input type="hidden" name="post_use_upload" class="hidden" value="0" />
<input type="hidden" name="post_file_upload" value="" class="hidden"  />
<input type="hidden" name="URL" value="<?php echo $file["URL"]; ?>" class="hidden">
<iframe width="0" height="0" frameborder="0" src="" name="uploader"></iframe>
<iframe width="0" height="0" frameborder="0" src="" name="poll"></iframe>
<h3>Post a Torrent</h3>
<script>
	upload();
</script>

<div 
<?php 

global $seeder;

if ( 
		! $seeder->enabled() || ! ($_GET["method"] == "torrent" || is_local_torrent($file["URL"]) )
		) echo 'style="display:none;"' ?> id="server_sharing">
<fieldset>
	<input type=checkbox name="SharingEnabled" value="1" 
<?php 
	global $settings;
	if ( $file["SharingEnabled"] || ( isset($settings["sharing_auto"]) && $settings["sharing_auto"] == 1 ) ) echo " checked"; 
?> /> Enable server sharing for this file
</fieldset>
</div>

<?php
	}
	else if ( $method == "upload" ) {
?>
	<input type="hidden" name="post_use_upload" class="hidden" value="1" />
  <input type="hidden" name="URL" value="<?php echo $file["URL"]; ?>" class="hidden">
	<h3>Upload a File</h3>
	<div id="upload_file">
	<input type="file" name="post_file_upload" value="Choose File" /><br />
	<p style="font-size: 11px; margin-bottom: 0px; padding-bottom: 0px;">
	<strong>Note:</strong> Uploading files with your browser can take several minutes or longer, 
	depending on the file size.  The file upload will begin when you click "Publish".  Please be patient 
	and do not touch the browser while your file is uploading.  Also be aware that servers sometimes have 
	a limit on the maximum size of an uploaded file.  For files larger than 2 or 3 megabytes, we generally 
	recommend either posting a torrent or using an FTP program and then linking to the file.<br /><br />
	The maximum upload size of this server is <strong><?php echo ini_get("upload_max_filesize"); ?></strong>.
	</p>
	</div>
<?php
	} // else if method == upload

	else if ( $method == "link" ) {
?>
	<input type="hidden" name="post_file_upload" value="" class="hidden"  />
	<input type="hidden" name="post_use_upload" class="hidden" value="0" />

	<div id="specify_url">
		<h3>URL of the file:</h3>
		<input type="text" name="URL" size="60" value="<?php echo $file["URL"]; ?>" />
	</div>
<?php
	} // else if method == link
} // if ( isset method )
else {
?>

<input type="hidden" name="OldURL" value="<?php echo $file["URL"]; ?>" class="hidden">
<input type="hidden" name="URL" value="<?php echo $file["URL"]; ?>" class="hidden">
<input type="hidden" name="post_file_upload" value="" class="hidden">
<?php
}
?>
</fieldset>

<fieldset id="video_blurb">
<?php
if ( is_local_torrent($file["URL"]) ) {
	$torrentfile = local_filename($file["URL"]);
?>
<input type="hidden" name="URL" value="<?php echo $file["URL"]; ?>" class="hidden">

<div style="color: #A00;">Sharing "<?php echo $torrentfile; ?>".<br /> 
<strong>You must keep the BM Helper window open for this file to remain available.</strong></div>

<?php
} // if is_local_torrent
else if ( is_local_file($file["URL"]) ) {
	global $actual_fname;
	if ( isset($actual_fname) && $actual_fname != "" ) {
		$filename = encode($actual_fname);
	}
	else if ( isset($file['FileName']) ) {
		$filename = $file['FileName'];
	}
	else {
		$filename = local_filename($file["URL"]);
	}
?>

<div style="color: #A00;">Uploaded "<?php echo $filename; ?>".<br /> </div>
<input type="hidden" name="actual_fname" value="<?php echo $filename; ?>" class="hidden">

<?php
}
else if ( $file["URL"] != "http://" ) {
?>
<div style="color: #A00;">Linked to "<a href="<?php echo $file["URL"]; ?>"><?php echo $file["URL"]; ?></a>".<br /> </div>
<input type="text" name="URL" size="60" value="<?php echo $file["URL"]; ?>" />
<?php
}
?>
	</fieldset>
</div>

<?php

	} 
	else {

?>

<input type="hidden" name="post_file_upload" value="" class="hidden" />
<input type="hidden" name="URL" value="<?php echo $file["URL"]; ?>" class="hidden">

<?php
	}
?>

<div class="section">

<fieldset id="channel_selection">
	<legend>Publish to These Channels</legend>
   <ul>

<?php
	$channels = $store->getAllChannels();
	foreach ($channels as $channel) {

		if ( is_admin() || $channel["OpenPublish"] ) {

			print("<li>");
						
			print("<input type=checkbox name=\"post_channels[]\" value=\"" . $channel['ID'] . "\"");
			if ( isset($file["post_channels"]) ) {
				foreach ( $file["post_channels"] as $channel_id ) {
					if ( $channel_id == $channel["ID"] ) {
						print(" checked=\"true\"");
						break;
					}
				}
			}

			if ($file["URL"] != "") {

				foreach ($channel["Files"] as $list) {
					if ($list[0] == $file["ID"]) {
						print(" checked=\"true\"");
						break;
					}
				}

			}

			print(" /> ");

			// display channel icon if we have one
			if ( isset($channel["Icon"]) && $channel["Icon"] != "" ) {
				print "<img src=\"" . $channel["Icon"] . "\" width=16 />&nbsp;";
			}

			print( $channel['Name'] . "<br/>\n");
		}
	}
?>

	    </ul>
</fieldset>


<fieldset>
<div class="the_legend">Title: </div><br /><input type="text" name="Title" size="38" value="<?php echo $file["Title"]; ?>"/>
</fieldset>

<fieldset>
       <div class="the_legend">Description (optional):</div><br /><textarea rows="4" cols="38" name="Description"><?php echo $file["Description"]; ?></textarea>
</fieldset>

<fieldset><div class="the_legend">Thumbnail (optional): </div>
<a href="#" onClick="document.getElementById('specify_image').style.display = 'none'; document.getElementById('upload_image').style.display = 'block'; return false;">Upload Image</a> or <a href="#" onClick="document.getElementById('upload_image').style.display = 'none'; document.getElementById('specify_image').style.display = 'block'; return false;">Specify URL</a>

<div style="display:none;" id="upload_image">
<input type="file" name="Image_upload" value="Choose Image" />
</div>


<div id="specify_image" style="display:<?php

	if ($file["Image"] == "" || $file["Image"] == "http://") {
		echo "none";
	} else {
		echo "block";
	}

?>;" >

<input type="text" name="Image" size="40" value="<?php echo $file["Image"]; ?>"/>

</div>
</fieldset>

<fieldset><img src="images/cc_logo_17px.png" alt="CC logo" /> Creative Commons (optional): <input type="text" name="LicenseName" size="38" value="<?php echo $file['LicenseName']; ?>" onFocus="this.blur();" autocomplete="off" class="blended"/><br/>

<a href="#" onClick="window.open('http://creativecommons.org/license/?partner=bmachine&exit_url=' + escape('<?php echo get_base_url(); ?>cc.php?license_url=[license_url]&license_name=[license_name]'),'cc_window','scrollbars=yes,status=no,directories=no,titlebar=no,menubar=no,location=no,toolbar=no,width=450,height=600'); return false;"><?php

	if ($file["LicenseURL"] == "") {
		echo "Choose";
	} else {
		echo "Change";
	}

?> License</a>

<input type="hidden" name="LicenseURL" value="<?php echo $file["LicenseURL"]; ?>" class="hidden"/>

</fieldset>
</div>


<p class="publish_button" style="clear: both;">
<input id="publish_button" style="border: 0px solid black;" type="image" src="images/publish_button.gif" border=0 alt="Continue" />
</p>

<div class="section optional">
<div class="section_header">Optional: Additional Information</div>

<?php
	$files = $store->getAllFiles();

  if ( count($files) > 0 ) {
?>
		<fieldset id="auto_fill">
		<legend>Auto Fill</legend>
		<div style="font-size: 12px; line-height: 15px;">Automatically fill in these information fields with info from a previously published video:</div>

<SCRIPT LANGUAGE="JavaScript">
<?php
  	if ( is_array($files) ) {
  		echo build_auto_fill($files);
	  }
?>
</script>
<?php
   	if ( is_array($files) ) {
 		  echo build_auto_select($files, $file["ID"]);
 	  }
  } // if ( count > 0 ) 
?>	
		</fieldset>

    <fieldset>
      <div class="the_legend">
			Creator (can be multiple or an organization)
			</div><br />
			<input type="text" name="Creator" size="40" value="<?php echo $file["Creator"]; ?>"/>
    </fieldset>

    <fieldset>
      <div class="the_legend">Associated Donation Setup:</div> 

<select name="donation_id">
<option value="">(none)</option>
<?php
	$donations = $store->getAllDonations();
	if ( is_array($donations) ) {
		foreach($donations as $id => $donation) {
			if ( isset($donation["title"]) && isset($donation["text"]) ) {
				print("<option value=" . $id);
				if (isset($file["donation_id"]) && $file["donation_id"] == $id ) {
					print(" selected=\"true\"");
				}
				print(">" . $donation["title"] . "</option>");
			} // if
		} // foreach
	}
?>
</select>

    </fieldset>

    <fieldset>
      <div class="the_legend">Copyright Holder (if different than creator)</div>
			<br />
			<input type="text" name="Rights" size="40" value="<?php echo $file["Rights"]; ?>"/>
    </fieldset>

    <fieldset>
      <div class="the_legend">Keywords / Tags (1 per line)</div>
			<br/>
			<textarea name="Keywords" rows="4" cols="38"><?php 
				foreach( $file["Keywords"] as $kw ) {
					print $kw . "\n";
				}
			?></textarea>
    </fieldset>

<fieldset style="clear:both" id="postdiv">
       <div class="the_legend">People Involved:</div>
<div id="people_header"><table cellpadding="2" cellspacing="0" border="0">
	<tr>
		<td width="200"><font class="the_legend">Name</font></td>
		<td width="200"><font class="the_legend">Role</font></td>
	</tr>
	</table>
</div>

<div id="people_holder"><table cellpadding="2" cellspacing="0" border="0" id="people_table">
	<tr>
		<td width="200">&nbsp;</td>
		<td width="200">&nbsp;</td>
	</tr>

<?php
	foreach ($file["People"] as $person_row) {
		if ( isset( $person_row[0] ) && isset( $person_row[1] ) ) {
?>
	<tr>
		<td><input type="text" name="People_name" value="<?php echo $person_row[0]; ?>" onKeyDown="isFull();"/></td>
		<td><input type="text" name="People_role" value="<?php echo $person_row[1]; ?>" onKeyDown="isFull();"/></td>
	</tr>
<?php
		}
	}
?>
	<tr>
		<td><input type="text" name="People_name" value="" onKeyDown="isFull();"/></td>
		<td><input type="text" name="People_role" value="" onKeyDown="isFull();"/></td>
	</tr>
</table>
</div>
</fieldset>

<fieldset style="clear:both" id="postdiv">

<div class="the_legend">
<a href="#" onClick="document.getElementById('transcript_upload').style.display = 'none'; document.getElementById('transcript_url').style.display = 'none'; document.getElementById('transcript_text').style.display = 'block'; return false;" style="font-weight:normal;">Enter Transcript Text</a> <em>or</em> <a href="#" onClick="document.getElementById('transcript_text').style.display = 'none'; document.getElementById('transcript_url').style.display = 'none'; document.getElementById('transcript_upload').style.display = 'block'; return false;">Upload text file</a> <em>or</em> <a href="#" onClick="document.getElementById('transcript_upload').style.display = 'none'; document.getElementById('transcript_text').style.display = 'none'; document.getElementById('transcript_url').style.display = 'block'; return false;">Specify URL</a>
</div>

<div id="transcript_text"<?php
	if ($file["Transcript"] != "") {
		print(" style=\"display:none;\"");
	}
?>>

<textarea rows="3" cols="40" 
	name="post_transcript_text"><?php 
		if ( isset($transcript_text) ) {
			echo $transcript_text;
		}
	?></textarea>
</div>

<div id="transcript_upload" style="display:none;">
<input type="file" name="post_transcript_file"/>
</div>

<div id="transcript_url"<?php
	if ($file["Transcript"] == "") {
		print(" style=\"display:none;\"");
	}
?>>

<input type="text" name="Transcript" size="40" value="<?php echo $file["Transcript"]; ?>"/>
</div>
</fieldset>

<fieldset>
  <div class="the_legend">Associated Webpage </div>
	<br />
	<input type="text" name="Webpage" size="40" value="<?php echo $file["Webpage"]; ?>"/>
</fieldset>


<fieldset>Release Date
<div class="input_sub">
Day: <select name="ReleaseDay">
	<option value=""></option>
<?php

	for ( $i=1; $i<=31; $i++ ) {
		print("<option value=" . $i);
		if ($i == $file['ReleaseDay']) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");
	}

?>
</select>

&nbsp;&nbsp;Month: <select name="ReleaseMonth">
	<option value=""></option>

<?php

	$months = array(
			"January", "February", "March", "April", "May", "June", 
			"July", "August", "September", "October", "November", "December");

	for ( $i = 0; $i < count($months); $i++ ) {

		print("<option value=" . $i);
		if ($file['ReleaseMonth'] != "" && $i == $file['ReleaseMonth']) {
			print(" selected=\"true\"");
		}
		print(">" . $months[$i] . "</option>");

	}

?>
</select>

&nbsp;&nbsp;Year: <input type="text" name="ReleaseYear" size="4" maxlength="5" value="<?php echo $file['ReleaseYear']; ?>"/>

</div>
</fieldset>

<fieldset>
Play Length

<div class="input_sub">
Hours: <input type="text" name="RuntimeHours" size="2" value="<?php echo $file['RuntimeHours']; ?>"/> Minutes: <select name="RuntimeMinutes">
	<option value=""></option>
<?php

	for ( $i=0; $i < 60; $i++ ) {

		$min = str_pad($i,2,'0',STR_PAD_LEFT);

		print("<option value=" . $min);
		if ($min == $file['RuntimeMinutes']) {
			print(" selected=\"true\"");
		}
		print(">" . $min . "</option>");
	}

?>

</select> Seconds: <select name="RuntimeSeconds">

	<option value=""></option>

<?php

	for ( $i=0; $i < 60; $i++ ) {

		$sec = str_pad($i,2,'0',STR_PAD_LEFT);

		print("<option value=" . $sec);
		if ($sec == $file['RuntimeSeconds']) {
			print(" selected=\"true\"");
		}
		print(">" . $sec . "</option>");
	}

?>

</select>&nbsp;&nbsp;&nbsp;<input type="checkbox" name="Excerpt"<?php if ($file['Excerpt']) {

	print(" checked=\"true\"");

}?>/> This is an excerpt of a longer piece.

</div>
</fieldset>


<fieldset><input type="checkbox" name="Explicit"<?php if ($file['Explicit']) {
	print(" checked=\"true\"");
}?>> Contains explicit content (some search services filter based on this).
</fieldset>

<fieldset>
Create Date

<div class="input_sub">
Will be set to the timestamp of the first time that publish the file.  
<a href="#" onClick="document.getElementById('create_time').style.display = 'block'; return false;">Manually Edit Create Date</a>
</div>

<div id="create_time" style="display:none;">
<select name="post_create_day">
<?php
	$createday = date("j",$file['Created']);

	for ( $i=1; $i<=31; $i++ ) {

		print("<option value=\"" . $i . "\"");
		if ($i == $createday) {
			print(" selected");
		}
		print(">" . $i . "</option>\n");

	}
?>
</select>

<select name="post_create_month">
<?php

	$createmonth = date("n",$file['Created']);

	$months = array(
			"January", "February", "March", "April", "May", "June", 
			"July", "August", "September", "October", "November", "December");

	for ( $i=0; $i < count($months); $i++ ) {

		print("<option value=" . $i);
		if ($i == ($createmonth-1)) {
			print(" selected=\"true\"");
		}
		print(">" . $months[$i] . "</option>");
	}
?>
</select>

<select name="post_create_year">
<?php

	$createyear = date("Y",$file['Created']);

	for( $i=2005; $i<2026; $i++ ) {

		print("<option value=" . $i);
		if ($i == $createyear) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");
	}
?>
</select> @

<select name="post_create_hour">
<?php

	$createhour = date("G",$file['Created']);

	for ($i=0; $i <= 23; $i++ ) {

		print("<option value=" . $i);
		if ($i == $createhour) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");
	}

?>
</select>:<select name="post_create_minute">

<?php
	$createminute = date("i",$file['Created']);

	for ( $i=0; $i < 60; $i++ ) {

		$min = str_pad($i,2,'0',STR_PAD_LEFT);

		print("<option value=" . $min);
		if ($min == $createminute) {
			print(" selected=\"true\"");
		}
		print(">" . $min . "</option>");
	}
?>
</select>
</div>
</fieldset>


<fieldset>
Timestamp

<div class="input_sub">
Will be set to the time that you press 'publish'. 
<a href="#" onClick="document.getElementById('publish_time').style.display = 'block'; return false;">Manually Edit Timestamp</a>
</div>

<div id="publish_time" style="display:none;">
<select name="post_publish_day">
<?php

	$publishday = date("j",$file['Publishdate']);

	for ( $i=1; $i <= 31; $i++ ) {

		print("<option value=" . $i);
		if ($i == $publishday) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");

	}
?>
</select>

<select name="post_publish_month">
<?php

	$publishmonth = date("n",$file['Publishdate']);

	$months = array(
			"January", "February", "March", "April", "May", "June", 
			"July", "August", "September", "October", "November", "December");

	for ( $i=0; $i < count($months); $i++ ) {

		print("<option value=" . $i);
		if ($i == ($publishmonth-1)) {
			print(" selected=\"true\"");
		}
		print(">" . $months[$i] . "</option>");
	}
?>
</select>

<select name="post_publish_year">
<?php
	$publishyear = date("Y",$file['Publishdate']);

	for( $i=2005; $i<2026; $i++ ) {
		print("<option value=" . $i);
		if ($i == $publishyear) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");
	}
?>
</select> @

<select name="post_publish_hour">
<?php

	$publishhour = date("G",$file['Publishdate']);
	for ($i=0; $i <= 23; $i++ ) {

		print("<option value=" . $i);
		if ($i == $publishhour) {
			print(" selected=\"true\"");
		}
		print(">" . $i . "</option>");
	}

?>
</select>:<select name="post_publish_minute">

<?php
	$publishminute = date("i",$file['Publishdate']);

	for ( $i=0; $i < 60; $i++ ) {

		$min = str_pad($i,2,'0',STR_PAD_LEFT);

		print("<option value=" . $min);
		if ($min == $publishminute) {
			print(" selected=\"true\"");
		}
		print(">" . $min . "</option>");
	}
?>
</select>
</div>
</fieldset>
</div>

<p class="publish_button" style="clear: both;">
<input style="border: 0px solid black;" type="image" src="images/publish_button.gif" border=0 alt="Continue" />
</p>

</div>
</form>
<?php
}

function build_auto_select($files, $id = "") {
	global $store;

	if ( is_array($files) && count($files) > 0 ) {
		$out = '<select name="videos" onChange="autofill(this.options[this.selectedIndex].value);" >';
		$out .= "<option value=\"$id\"></option>\n";
		foreach($files as $file["ID"] => $file) {
			$out .= '<option value="' . $file["ID"] . '">' . $file["Title"] . '</option>';
		}
	
		$out .= '</select>';
		return $out;
	}
}
		
function build_auto_fill($files) {

	$js = '
	function autofill(id) {
		clearPeople();
		frm = document.getElementById("post");

    if ( id == "" ) {
     frm.reset();
     addPeople();
    }
	';

	foreach($files as $id => $file) {

		$js .= '
		if ( id == "' . $id. '") {
		';

		if ( isset($file["Creator"]) ) {
			$js .= 'frm.Creator.value = "' . urlencode($file["Creator"]) . '";';
		}
		else {
			$js .= 'frm.Creator.value = "";';		
		}

		if ( isset($file["donation_id"]) ) {
			$js .= 'frm.donation_id.value = "' . $file["donation_id"] . '";';
		}
		else {
			$js .= 'frm.donation_id.value = "";';		
		}

		if ( isset($file["Rights"]) ) {
			$js .= 'frm.Rights.value = "' . urlencode($file["Rights"]) . '";';
		}
		else {
			$js .= 'frm.Rights.value = "";';		
		}

		if ( isset($file["Keywords"]) ) {
			$js .= 'frm.Keywords.value = "' . urlencode(join($file["Keywords"], ' ')) . '";';
		}
		else {
			$js .= 'frm.Keywords.value = "";';		
		}

		if ( isset($file["Webpage"]) ) {
			$js .= 'frm.Webpage.value = "' . $file["Webpage"] . '";';
		}
		else {
			$js .= 'frm.Webpage.value = "";';		
		}

		if ( isset($file["Explicit"]) && $file["Explicit"] == 1 ) {
			$js .= 'frm.Explicit.checked = true;';
		}
		else {
			$js .= 'frm.Explicit.checked = false;';
		}


		$file["People"] = $file['People'];
		if ( count($file["People"]) > 0 ) {
			foreach ($file["People"] as $person_row) {
				if ( isset( $person_row[0] ) && isset( $person_row[1] ) && 
						$person_row[0] != "" && $person_row[1] != "" ) {
					$js .= "addPerson('" . trim($person_row[0]) . "', '" . trim($person_row[1]) . "');";
				}
			}
		}

		$js .= "addPeople();";		

		$js .= '}';
	
	}

	$js .= '}';
	return $js;

} // build_auto_fill

function build_mime_chooser() {

	$mime_value = "video/unknown";
	$mime_options = array();
	
	$mime_options["video/unknown"] = "Video";
	$mime_options["audio/unknown"] = "Audio";
	$mime_options["application/x-bittorrent"] = "Torrent";
	$mime_options["application/octet-stream"] = "Unknown";
	
	$out = "<strong>Broadcast Machine can't figure out what kind of file this is.  Please choose an option below.</strong>
<div id=\"mime_choosers\">
This file is a :<br>";

	foreach( $mime_options as $type => $text ) {

		$out .= "<input type=\"radio\" name=\"mime_chooser\" value=\"" . $type . "\"";
		if ( $mime_value == $type ) {
			$out .= " checked";
		}
		$out .= "> $text<br />";
	}
	$out .= "<input type=\"radio\" name=\"mime_chooser\" value=\"other\" /> Other: <input type=\"text\" name=\"mime_chooser_custom\" size=\"15\" value=\"\" /> <br />";
	$out .= "</div>";

	return $out;

}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */
?>