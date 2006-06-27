<?php

// I hate PHP
if (get_magic_quotes_gpc()) {
   $_GET    = array_map('stripslashes', $_GET);
}

// Returns an array of URLs passed on the command line
// Should either be in the form http://thisserver/thisdir/url or
// http://thisserver/thisdir/?url1=url1&url2=url2&url3=url3
function getURLList() {
  $base = '/subscribe-test2/';
  $url = substr($_SERVER['REQUEST_URI'],strlen($base));
  if ($url[0] != '?') {
    return array($url);
  } else {
    $urls = array();
    $count = 1;
    while (isset($_GET['url'.$count])) {
      $urls[] = $_GET['url'.$count];
      $count++;
    }
    return $urls;
  }
}

function getLink ($base, $urls) {
  
  $out = $base;
  $link = '?';
  $count = 1;

  foreach ($urls as $url) {
    $out .= $link.'url'.$count.'='.urlencode($url);
    $link = '&amp;';
    $count++;
  }
  return $out;
}

// Returns a link to the page that generates OPML for this list of URLs
function getSubscribeLink($urls) {
  $base = '/subscribe-test2/opml.php';
  return getLink ($base, $urls);
}

function getInstallerLink($urls) {
  $base = '/subscribe-test2/installer.php';
  return getLink ($base, $urls);
}

$URLList = getURLList();
$SubscribeLink = getSubscribeLink($URLList);

?><html>
<head>
<title>Subscribing to Democracy TV channel</title>
</head>
<body>

<div class="top">
 A custom Democracy subscription file to subscribe you to the
 following URLs is being created. If it doesn't open automatically,
 <a href="<?php echo $SubscribeLink; ?>">click here</a> to download it.
</div>

<div>
 To install Democracy on windows with the given channels,
 <a href="<?php echo getInstallerLink($URLList); ?>">click here.</a>
</div>
<ul>
<?php
foreach ($URLList as $url) {
print "<li>".htmlentities($url)."</li>";
}
?>
</ul>
</body>
