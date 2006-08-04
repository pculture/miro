<?php
/**
 * trigger the Broadcast Machine torrent helper when doing an upload
 * @package BroadcastMachine
 */

require_once("include.php");

if (!isset($_GET['hash'])) {
?>

<html>
<head></head>

<body <?php if (can_upload()) { ?>onLoad="javascript:sendUpload();"<?php }?>>
<?php
	if (can_upload()) {
		draw_detect_scripts();
		draw_upload_link();
	} 
	else {
		echo '<script language="javascript">alert("Sorry, you don\'t have permission to upload");</script>';
	}
?>
</body>
</html>

<?php 
} 
// We already have a hash
else { 

	$arr =  array (
		"announce_url" => preg_replace('|^http://.*?(/.*)$|','\\1',get_base_url()).'announce.php',
		"blog_torrent_version" => "0.1",
		"hash" => $_GET['hash'],
		"server_name" => $_SERVER['HTTP_HOST'],
		"upload_url" => preg_replace('|^http://.*?(/.*)$|','\\1',get_base_url()).'upload.php',
		"username" => get_username()
	);
	
	$data = bencode($arr);


	if (isset($_GET['type']) && $_GET['type'] == 'exe') {
	  send_installer('Blog_Torrent_Upload',$data);
	} 
	else if (isset($_GET['type']) && $_GET['type'] == 'mac') {
	  send_mac_uploader('Blog_Torrent_Upload',$data);
	} 
	else {

		// cjm - this code wasn't working on all servers (in particular, the pculture server),
		// until I added the Accept-Ranges, Connection, and Content-Length headers (06/29/2005)
		header('Accept-Ranges: bytes', true);
		header('Connection: close', true);
		header('Content-type: application/x-blogtorrent');
		header('Content-Disposition: inline; filename="upload.blogtorrent"');
		header('Content-Length: ' . strlen($data));

		echo $data;
		exit;

    // in lieu of that, this line always works (but it isn't as nice for the user)
    //	  header('Content-Disposition: attachment; filename="upload.blogtorrent"');

	}

}

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */
?>