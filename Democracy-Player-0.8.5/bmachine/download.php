<?php
/**
 * file download handler
 *
 * there's logic here to handle torrents, local files, external URLs, and also
 * making sure that the user has permission to get the file, and starting an
 * auth request if they don't.
 * @package BroadcastMachine
 */


require_once("include.php");

global $settings;
global $store;


if ( !isset($_GET["type"]) ) {
  $_GET["type"]= "direct";
}

// processing here in case our rewrite rules choke
if ( !isset($_GET["i"]) && !isset($_GET["c"]) && !isset($_GET["type"]) ) {
	$params = split("/", $_SERVER['REQUEST_URI']);

  $_GET["c"] = $params[ count($params) - 2 ];
  $_GET["i"] = $params[ count($params) - 1 ];
  $_GET["type"]= "direct";
  //$_SERVER["PHP_SELF"] = $_SERVER["SCRIPT_NAME"];
}

//
// just serve up the helper
//
if ( isset($_GET["type"]) && !isset($_GET["i"]) && !isset($_GET["c"]) ) {
	send_helper($_GET["type"]);
	exit;
}

// if this is an admin user, let them download even if there's no channel specified
if ( is_admin() && !isset($_GET["c"]) ) {
	$_GET["c"] = -1;
}

// we'll get this if doing a mod_rewrite
if ( isset($_GET["file"]) ) {
	$i = $store->getHashFromFilename($_GET["file"]);
}
else if ( isset($_GET["i"]) ) {
	$i = $_GET["i"];
}

//
// if the link doesnt have valid file/channel, then don't process it
//
if ( (!isset($i) || !isset($_GET["c"]) ) ) {
  header('HTTP/1.0 404 Not Found');
  echo "Invalid link";
  exit;
}


if ( stristr($i, ".") ) {
	$tmp = split("\.", $i);
	$i = $tmp[0];
}
$file = $store->getFile($i);
	 
if ( !isset($file) ) {
	header("HTTP/1.0 404 Not Found");
	print("Couldn't find your file");
	exit;
}

$channel = $store->getChannel($_GET["c"]);

if ( ! is_admin() ) {
	
	if ( !isset($channel) ) {
		die("Couldn't find channel");
	}

	if ( ! $store->channelContainsFile($i, $channel) ) {
		header("HTTP/1.0 404 Not Found");
		print("Couldn't find your file");
		exit;
	}

}



//
// if we require the user to be logged in to access the file, then do the HTTP AUTH now
//
if ( !isset( $_SESSION['user'] ) && 
     (
      ( isset($settings["DownloadRegRequired"]) && $settings["DownloadRegRequired"] == 1 ) || 
      ( isset($channel["RequireLogin"]) && $channel["RequireLogin"] == 1 )
      )) {
  
  // do an http auth here instead of redirecting to a page (1201469)
  do_http_auth();
  
}

/*
 *
 * at this point, the user is authed, and we just need to go through the process
 * of actually serving the file.
 *
 */

$filename = local_filename($file["URL"]);

//
// special handling for sending our helper installer files.  someday this will be broken out
// into its own file
//
if (isset($_GET["type"]) && ($_GET["type"] != "direct"  && $_GET["type"] != "helper") ) {
	send_helper($_GET["type"], $file);
} 

if ( is_local_file($file["URL"]) && 
			( ! is_local_torrent($file["URL"]) || ( isset($_GET["type"]) && $_GET["type"] == "direct" ) )
) {

	// if we have a junky mimetype, just set it to application/octet-stream - this
	// should help ensure that the file isn't downloaded as text by mistake
	if ( beginsWith($file["Mimetype"], "text") ) {
		$file["Mimetype"] = "application/octet-stream";
	}

  header('Content-type: ' . $file["Mimetype"] );
	
	// if we have the actual filename stored for this file, then send it instead of the hash
	if ( isset($file['FileName']) && $file['FileName'] != '' ) {
    $tmpname = $file["FileName"];
  }
  else {
    $tmpname = $filename;
  }

  header('Content-Disposition: attachment; filename="' . urlencode($tmpname) . '"');	
  header('Content-length: ' . filesize('./torrents/' . $filename));
  echo file_get_contents( './torrents/' . $filename );

  // make a note of this download for stat purposes
  $store->recordStartedDownload($file["ID"], is_local_torrent($file["URL"]) );
  exit;
}


if ( !is_local_file($file["URL"] ) ) {
  header('Location: ' . linkencode($file["URL"]));
  $store->recordStartedDownload($file["ID"], false );
  exit;
}

if ( is_local_torrent($file["URL"]) ) { 
  $onload = "javascript:sendTorrent();";
}
else {
  $onload = "";
}

//header("Content-type: text/html; charset=utf-8");
front_header($file["Title"] . ": Download",
	     $_GET["c"],
	     $channel["CSSURL"],
       rss_link( $_GET["c"] ),
	     $onload);

draw_detect_scripts();
draw_download_link($file, $channel, $i); 

front_footer($_GET["c"]);

/*
//
// special handling for if this file is on our server, but only if it's a .torrent file
//
if ( is_local_file($file["URL"] ) ) {

  $filename = local_filename($file["URL"]);
  //
  // process local torrents
  //
  if ( is_local_torrent($file["URL"] ) ) {
    
    header('Content-type: application/x-bittorrent');
    header('Content-Disposition: inline; filename="' . urlencode($filename) . '"');
    header('Content-length: ' . filesize('./torrents/'.$filename));
    
    // make sure the seeder is running, if it should be
    $torrenthash = $store->getHashFromTorrent($filename);
    $seeder->confirmSeederRunning($torrenthash, $filename);
    
    echo $store->getRawTorrent($filename);
  }
  
  //
  // process other local files
  //
  else {
    header('Content-type: ' . $file["Mimetype"] );
    header('Content-Disposition: inline; filename="' . urlencode($filename) . '"');
    header('Content-length: ' . filesize('./torrents/' . $filename));
    echo file_get_contents( './torrents/' . $filename );
  }

  exit;
}


//
// otherwise, just serve the file and be done
//

// urlencode the filename so that we don't send junky chars to the user (1201465)
header('Location: ' . linkencode($file["URL"]));
*/

function draw_download_link($file, $channel, $i) {

  //  $file = preg_replace('/^(.*)\.torrent$/','\\1',$filename);
	$filename = $file["Title"];
	//$url = "download.php?c=" . $_GET["c"] . "&i=" . $i;
	$url = download_link($_GET["c"], $i, true);
  $url = str_replace("&amp;", "&", $url);

?>
<script  language="JavaScript" type="text/javascript" ><!--

if (hasMac()) {
  document.writeln("<h1>How to download <?php echo htmlspecialchars($filename) ?> on Mac</h1>");

  if (hasBlogTorrent()) {
		document.writeln("<p>It looks like you already have Broadcast Machine Helper installed. Your download should have started. If you have pop-ups blocked, click <a href=\"<?php echo $url; ?>&type=torrent\">the .torrent file</a> to start your download.</p>");
		document.writeln("<p>If your Broadcast Machine Helper install is damaged, you can reinstall it from <a href=\"<?php echo $url; ?>\">BlogTorrent.zip</a>.</p>");
  } 
	else {
		document.writeln("<p>It looks like you haven't installed Broadcast Machine Helper, yet. To install it, you need to download a small file called <a href=\"<?php echo $url; ?>&type=mac\">BlogTorrent.zip</a>. Save it to your desktop and double click on it to unstuff it. Then double click on the Broadcast Machine Helper application to begin downloading <?php echo htmlspecialchars($filename) ?> using Broadcast Machine Helper.</p>");
		document.writeln("<p>If you already have Broadcast Machine Helper or another BitTorrent client, click <a href=\"<?php echo $url; ?>&type=torrent\">the .torrent file</a> to start your download.</p>");
  }

  document.writeln("<br /><br /><br /><p class=\"small\"><a href=\"download.php?type=exe&amp;file=<?php echo urlencode($filename) ?>\">The Windows installer</a> for your download is available here if you need it.</p>");

} else if (hasWindows()) {
	document.writeln("<h1>Downloading <?php echo htmlspecialchars($filename) ?></h1>");
	document.writeln("<p>If your download didn't start up, don't worry.  You just need to <a href=\"<?php echo $url; ?>&type=exe\">get Broadcast Machine Helper</a>.</p>");
	document.writeln("<p>After the download, to start installation, click \"open\" and \"run\".  Since installing a program can be a security risk, you may be prompted with security warnings. Just click \"Yes\" to proceed.</p>");
	document.writeln("<p>Once you download and install Broadcast Machine Helper, it will automatically start fetching the file you want.</p>");


  document.writeln("<p>If you already have Broadcast Machine Helper or another BitTorrent client installed, <a href=\"<?php echo $url; ?>&amp;type=torrent\">the .torrent file</a> is available here.</p>");


  document.writeln("<br /><br /><br /><p class=\"small\"><a href=\"<?php echo $url; ?>&amp;type=mac\">The Mac installer</a> for your download is available here if you need it.</p>");
} 
else {
    //Non-Windows, Non-Mac platform
	document.writeln("<h1>Downloading <?php echo htmlspecialchars($filename) ?></h1>");
	document.writeln("<p>Since you're not using Windows or Mac, chances are you can figure out Bit Torrent yourself, without the help of Broadcast Machine Helper. If you already have a BitTorrent client installed, <a href=\"<?php echo $url; ?>&type=torrent\">this link</a> should automatically start your download.</p>");
	document.writeln("<p>Otherwise, you just need to <a href=\"http://bittorrent.com/download.html\">get a BitTorrent client for your platform</a>.</p>");
  document.writeln("<p>Broadcast Machine Helper makes the whole process much easier, but there isn't a version for your platform, yet. You can help fix that by <a href=\"http://blogtorrent.com/donate\">donating</a> or helping to port it yourself.</p>");
  document.writeln("<br /><br /><br /><p class=\"small\"><a href=\"<?php echo $url; ?>&amp;type=exe\">The Windows installer</a> and <a href=\"<?php echo $url; ?>&amp;type=mac\">The Mac installer</a> for your download are available if you need either.</p>");
}


function sendTorrent() {
  if (hasBlogTorrent()) {

    myurl = "<?php echo $url; ?>";

    if ( hasWindows() ) {
      myurl = myurl + "&type=exe";
    }
    else if ( hasMac() ) {
      myurl = myurl + "&type=mac";
    }
    else {
      myurl = myurl + "&type=torrent";
    }
		//alert(myurl);
		window.open(myurl, 'download', 'width=300,height=200');
  }
}
--></script>
<noscript>
<h1>Downloading <?php echo htmlspecialchars($filename) ?></h1>
<p>If your download didn't start up, don't worry.  You just need to get Broadcast Machine Helper</p>

<p><a href="download.php?type=exe&amp;file=<?php echo urlencode($filename) ?>">Get Broadcast Machine Helper for Windows</a>.</p>

<p><a href="download.php?type=mac&amp;file=<?php echo urlencode($filename) ?>">Get Broadcast Machine Helper for Mac</a>.</p>

<p>After the download, to start installation, click "open" and "run".  Since installing a program can be a security risk, you may be prompted with security warnings. Just click "Yes" to proceed.</p>

<p>Once you download and install Broadcast Machine Helper, it will automatically start fetching the file you want.</p>

<p>If you already have Broadcast Machine Helper or another BitTorrent client installed, <a href="<?php echo $url; ?>">the .torrent file</a> is available here.</p>

<p>Broadcast Machine Helper is <a href="http://www.gnu.org/philosophy/free-sw.html">Free Software</a>, made by volunteers, with no ads or spyware.  If you'd like to learn more about Broadcast Machine Helper, check out their <a href="http://www.blogtorrent.com/">homepage</a>.</p>

<p>Broadcast Machine Helper is a <a href="http://downhillbattle.org/">Downhill Battle</a> project. We depend on your donations to continue developing software like this. <a href="http://blogtorrent.com/donate">Donate and help support this project</a>.</p>
</noscript>
<?php
}


function send_helper($type, $file = null) {

	if ( $file == null ) {
	
    if ($type == 'exe') {
      send_installer("Broadcast_Machine_Upload");
    }
    else if ($type == 'mac') {
      send_mac_installer("Broadcast_Machine_Upload");
    }
	}
  else if ( is_local_torrent($file["URL"]) ) {

		global $store;
		global $seeder;

		$filename = local_filename($file["URL"]);

		// make sure the seeder is running, if it should be
		$torrenthash = $store->getHashFromTorrent($filename);
		$seeder->confirmSeederRunning($torrenthash, $filename);
		
		$data = $store->getRawTorrent($filename);

    if ($type == 'exe') {
      send_installer($filename, $data);
    }
    else if ($type == 'mac') {
      send_mac_installer($filename, $data);
    }
    else if ($type == 'torrent' || $type == 'direct' ) {
      header('Content-type: application/x-bittorrent');
      header('Content-Disposition: inline; filename="' . urlencode($filename) . '"');
      header('Content-length: ' . filesize('./torrents/'.$filename));
      
			echo $data;
    }

    exit;
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