<?php
global $settings;
print '<?xml version="1.0" encoding="utf-8"?>';
?>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title><?php if (isset($pagename) && $pagename != "") { print($pagename); } else { print "Broadcast Machine"; } ?></title>
  <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<?php
print theme_css();
print theme_javascript();
if ( isset($feed) && $feed != "" ) {
  print('<link rel="alternate" type="application/rss+xml" title="RSS 2.0" href="' . $feed . '" />');
}
?>
<base href="<?php print get_base_url(); ?>" />
</head>

<?php
if ( $onload != "" ) {
  print '<body onload="' . $onload . '">';
}
else {
  print "<body>";
}
?>

<!--HEADER-->
<div id="header">
  <div id="header-inner">
  <div id="avatar"><a href="<?php print get_base_url(); ?>"><img src="<?php print site_image(); ?>" alt="" width="48" height="48" /></a></div>
  <h1><a href="<?php print get_base_url(); ?>"><?php print site_title(); ?></a></h1>
  <h2><?php print $pagename; ?></h2>
</div>

</div>
<!--/HEADER-->

<!--CONTENT-->
<div id="content">

	<!--INNER CONTAINER-->
	<div id="content-inner">
