<?php

// I hate PHP
if (get_magic_quotes_gpc()) {
   $_GET    = array_map('stripslashes', $_GET);
}

function getURLs() {
  $urls = array();
  $count = 1;
  while (isset($_GET['url'.$count])) {
    $urls[] = $_GET['url'.$count];
    $count++;
  }
  return $urls;
}

function wrapString($url) {
  $url = htmlspecialchars($url);
  return '<outline text="' . $url . '" type="rss" version="RSS2" xmlUrl="' . $url . '"/>
';
}

function getOPML() {
  $dateString = htmlentities(date("r"));
  $output = '<?xml version="1.0" encoding="UTF-8"?>
';
  $output = $output . <<< EOT
<opml version="2.0">
	<head>
		<title>Democracy Subscriptions</title>
		<dateCreated><?php print $dateString;?></dateCreated>
		<dateModified><?php print $dateString;?></dateModified>
	</head>
	<body>

EOT;
  $output = $output . join ("", array_map("wrapString", getURLs()));
  $output = $output . <<< EOT
</body>
</opml>
EOT;
  return $output;
}
?>
