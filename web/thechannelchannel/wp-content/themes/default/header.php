<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
	<title>Show Us the War</title>
	<link rel="stylesheet" href="wp-content/themes/default/hpcm.css" type="text/css" />
<!--	<link rel="stylesheet" href="wp-content/themes/default/frontpage3.css" type="text/css" /> -->
	<link href="<?php bloginfo('rss2_url'); ?>" rel="alternate" title="Show Us the War RSS" type="application/rss+xml" />

    <script src="/javascripts/prototype.js" type="text/javascript"></script>
    <script src="/javascripts/effects.js" type="text/javascript"></script>
    <script src="/javascripts/scriptaculous.js" type="text/javascript"></script>
</head>
<body>


<div id="page">


<!--

<div id="header">
	<div id="topimg">

		<span>
		<script type="text/javascript">
			var MONTH_NAMES=new Array('January','February','March','April','May','June','July','August','September','October','November','December','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec');
			var today = new Date();
			var month = today.getMonth();
			var day = today.getDate();
			var year = today.getFullYear();
			document.write(MONTH_NAMES[month] + ' ' + day + ', ' + year);
		</script>
		</span>
		<a href="/"><img src="http://www.huffingtonpost.com/images/header.gif" width="720" height="66" alt="The Huffington Post" /></a>
	</div>
	<ul id="topnav">
		<li id="home"><a href="http://www.huffingtonpost.com/" class="toplevel">Home</a></li>
		<li id="news"><a href="http://www.huffingtonpost.com/thenewswire/" class="toplevel">The News</a></li>
		<li id="blog"><a href="http://www.huffingtonpost.com/theblog/" class="toplevel">The Blog</a></li>

		<li id="festival"><a href="http://cf.huffingtonpost.com/" class="toplevel">Contagious Festival</a></li>
		<li id="features"><a href="http://www.huffingtonpost.com/features/" class="toplevel">Features</a>
			<ul id="etp">
				<li><a href="http://www.huffingtonpost.com/politics-aside/">Politics Aside</a></li>
				<li><a href="http://www.huffingtonpost.com/eat-the-press/">Eat The Press</a></li>
				<li><a href="http://www.huffingtonpost.com/russertwatch/">Russert Watch</a></li>

				<li><a href="http://www.huffingtonpost.com/news/">Hot Topics</a></li>
			</ul>
		</li>
		<li id="contact"><a href="http://www.huffingtonpost.com/contact/" class="toplevel">Contact Us</a></li>
	</ul>
</div>

-->



<div id="header_forms">
				<?php include (TEMPLATEPATH . '/searchform.php'); ?>







<!-- MAILING LIST -->

<script language="Javascript" type="text/javascript">

var fieldstocheck = new Array();
    fieldnames = new Array();

function checkform() {
  for (i=0;i<fieldstocheck.length;i++) {
    if (eval("document.subscribeform.elements['"+fieldstocheck[i]+"'].value") == "") {
      alert("Please enter your "+fieldnames[i]+".");
      eval("document.subscribeform.elements['"+fieldstocheck[i]+"'].focus()");
      return false;
    }
  }

  document.subscribeform.elements["emailconfirm"].value = document.subscribeform.elements["email"].value;

  return true;
}


function addFieldToCheck(value,name) {
  fieldstocheck[fieldstocheck.length] = value;
  fieldnames[fieldnames.length] = name;
}

function showIndicator() {
  Element.show('list_indicator');
}

function highlightResponse() {
  new Effect.Highlight('mailing_list');
}


</script>

<div id="mailing_list">

<span class="subscribe_text">Get news and video updates:</span>

  <form action="/mailinglist/?p=subscribe" method="post" onsubmit="showIndicator(); new Ajax.Updater('mailing_list', '/mailinglist/?p=subscribe', {asynchronous:true, evalScripts:true, onComplete:function(request){highlightResponse()}, parameters:Form.serialize(this)}); return false;">
    <input type=text name=email value="your email" size="20">
    <script language="Javascript" type="text/javascript">addFieldToCheck("email","email address");</script>
    <input type=hidden name="emailconfirm" value=""  />
    <input type=hidden name="htmlemail" value="1"  />
    <input type=hidden name="list[3]" value="signup" />
    <input type=hidden name="listname[3]" value="General Notification"/>
    
    
<input type=submit name="subscribe" value="Subscribe">
    <img alt="Indicator" class="spinner" height="5" id="list_indicator" src="/wp-content/themes/default/images/indicator.gif" style="display:none; vertical-align: middle" width="21" />
  </form>
</div>

  <!-- END MAILING LIST -->

</div>


<div id="page_title">
<a href="/"><img src="wp-content/themes/default/images/lens2.gif" alt="Show Us the War" /></a><br />
&nbsp;A collaborative, real-time documentary news project. <!-- In association with the <a style="color: #777;" href="http://www.huffingtonpost.com">Huffington Post</a>. -->
</div>


