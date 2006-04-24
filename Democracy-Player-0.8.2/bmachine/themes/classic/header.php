<?php
	global $settings;

	header("Content-type: text/html; charset=utf-8");
	print '<?xml version="1.0" encoding="utf-8"?>';
?>

	global $settings;

	header("Content-type: text/html; charset=utf-8");

	$site = site_title();	
	if ( $site != "" ) {
		$pagename = "$site: $pagename";
	}

	print("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
<title>");

	if ($pagename) {
	  print($pagename);
	}

	print("</title>
<meta http-equiv=\"Content-Type\" content=\"text/html;charset=utf-8\" />
<link rel=\"stylesheet\" type=\"text/css\" href=\"" . $stylesheet . "\"/>\n");

	if ( $feed != "" ) {
		print "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"RSS 2.0\" href=\"$feed\" />";
	}

	print("\n</head>\n");

  if ( $onload != "" ) {
    print "<body onload=\"$onload\">";
  }
  else {
    print "<body>";
  }

   print ("
<div id=\"wrap\">
<div id=\"inner_wrap\">
<div id=\"login_links\">");

	if (!(isset($_SESSION['user']) && is_array($_SESSION['user']))) {

		print("<a href=\"login.php?f=1\">Login</a>");
		if ( isset($settings['AllowRegistration']) && $settings['AllowRegistration'] == 1 ) {
			print (" | 
					<a href=\"newuser.php?f=1\">Register</a>");
		}

	} 
	else {

		global $can_use_cookies;
		if ( $can_use_cookies ) {
			print("<a href=\"login.php?f=1&logout=1\">Logout</a> ");
		}
		
		if ( is_admin() ) {
			print("| <a href=\"admin.php\">Admin</a>");		
		}

	}

	if (can_upload()) {

		print(" | <a href=\"publish.php\">Post a File</a>");

	}

	print("</div>
	<div id=\"library_header_wrap\">
	<div id=\"library_title\">" . $pagename . "</div>\n");

	if ( $channelID ) {
		$rsslink = '<a href="rss.php?i=' . $channelID . '"><img src="images/rss_button.gif" alt="rss feed" border="0" /></a>';
		print("<div id=\"rss_feed\">$rsslink</div>\n");
	}

	print("</div>\n\n");
