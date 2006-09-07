<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">


<html xmlns="http://www.w3.org/1999/xhtml">
<head>
	<title>Show Us the War</title>
	<link rel="stylesheet" href="wp-content/themes/hgm/style.css" type="text/css" />
	<link href="<?php bloginfo('rss2_url'); ?>" rel="alternate" title="Show Us the War RSS" type="application/rss+xml" />

    <script src="/javascripts/prototype.js" type="text/javascript"></script>
    <script src="/javascripts/effects.js" type="text/javascript"></script>
    <script src="/javascripts/scriptaculous.js" type="text/javascript"></script>
</head>
<body bgcolor="#ECECEC" leftmargin="0" topmargin="0" marginwidth="0" marginheight="0">
<!-- Begin container table -->
<table width="980" border="0" cellpadding="0" cellspacing="0">

	<tr valign="top">
		<td class="leftcolumn" width="222">
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

<span class="subscribe_text">News and Video Updates:</span>

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

		
		</td>
		<td bgcolor="#FFFFFF" width="678">

<!-- logo and tag area -->
		<div id="page_title">
			<a href="/"><img src="/wp-content/themes/hgm/images/sutw_logo.gif" border="0" alt="Show Us the War" /></a>
			<br />
			&nbsp;A collaborative documentary news project.
			<br>
			<span class="subheader">bringing you the best independent and unembedded journalism, soldiers' stories &amp; news from the ground in Iraq </span>
		</div>

		</td>
		<td class="rightcolumn" width="92">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="112" alt=""></td>
	</tr>
	<!--HEADER END-->
		
	


