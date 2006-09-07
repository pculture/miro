<?echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"; ?> 
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd"> 

<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" > 
<head> 
<title>RADIO.BLOG</title> 
<meta http-equiv="Content-Type" content="application/xhtml+xml; charset=UTF-8" /> 
<link rel="stylesheet" type="text/css" href="style.css" /> 
<link rel="stylesheet" type="text/css" href="banner.css" /> 
</head>
<body> 

<div>
<object type="application/x-shockwave-flash" data="radioblog.swf?autoplay=<? echo $_GET['autoplay']; ?>" width="220" height="300"> 
<param name="src" value="radioblog.swf?autoplay=<? echo $_GET['autoplay']; ?>" /> 
<param name="quality" value="high" /> 
<param name="movie" value="radioblog.swf?autoplay=<? echo $_GET['autoplay']; ?>" /> 
<param name="menu" value="false" /> 
</object>
</div>

<!-- BANNER -->
<? include("banner.php"); ?>
<!-- END BANNER -->

</body> 

</html>