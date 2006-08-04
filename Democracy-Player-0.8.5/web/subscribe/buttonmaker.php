<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>

<title>Democracy - Internet TV Platform - Free and Open Source</title>


<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />

<link href="/css/layout.css" rel="stylesheet" type="text/css" />
<link rel="shortcut icon" type="image/ico" href="http://getdemocracy.com/favicon.ico" />

<link rel="alternate" type="application/rss+xml" title="RSS 2.0" href="http://getdemocracy.com/news/feed" />

<script src="/js/prototype.js" type="text/javascript"></script>
<script src="/js/scriptaculous.js" type="text/javascript"></script>
<script src="/js/effects.js" type="text/javascript"></script>
<script src="/js/mailinglist.js" type="text/javascript"></script>

<script language="javascript">

var originalButtonsHTML;

function saveOriginalButtonsHTML()
{
  originalButtonsHTML = document.getElementById('generated_buttons').innerHTML;
}

function generateButtons()
{
  var buttonHTML = '';
  var i;
  var errorString = '';
  var urlInput;
  var urls;
  var subscriptionUrl = "http://subscribe.getdemocracy.com/subscribe.php?";
  
  // add new buttons here
  // add url to button img
  // (make sure to add comma to current last img)
  var buttons = new Array(
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-01.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-02.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-08.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-09.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-15.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-16.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-10.gif',
    'http://www.getdemocracy.com/buttons/img/subscribe-btn-14.gif'
  );
  
  document.getElementById('generated_buttons').innerHTML = originalButtonsHTML;
  
  
  urlInput = document.getElementById('urls').value;

  if (urlInput == null || urlInput == '')
  {
    errorString = "You need to enter at least one valid URL.  Please try again in the above field.";
  }
  else
  {
    urls = urlInput.split('\n');

    for (i = 1; i <= urls.length; i++)
    {
      subscriptionUrl += "url" + i + "=" + escape(urls[(i - 1)]);

      if (i != urls.length)
      {
        subscriptionUrl += "&";
      }
    }
  }
  
  
  for (i=0; i < buttons.length; i++)
  {
    buttonHTML += '<div class="button"><div class="image"><img src="' + buttons[i] +
      '" alt="" /></div><div class="code"><textarea name="code" cols="38" rows="4" style="background-color: #EEEEEE;"><a href="' + subscriptionUrl + '" title="Democracy: Internet TV"><img src="'+ buttons[i] + '" alt="Democracy: Internet TV" border="0" /></a></textarea></div></div>';
  }
  
  document.getElementById('subscription_url_link').innerHTML = 
    '<a href="' + subscriptionUrl + '">' + subscriptionUrl + '</a>';
  document.getElementById('buttons').innerHTML = buttonHTML;
  
  if (errorString != null && errorString != '')
  {
    document.getElementById('generated_buttons').innerHTML = 
   '<p><strong>Error!</strong></p><p>' + errorString + '</p>';
  }
  
  Effect.SlideDown('generated_buttons')
}
</script>
	
</head>
	
	
<style>

#channel_list {
margin-top: 20px;
padding: 10px;
background-color: #f5f5f5;
}

#install_info {
padding-top: 15px;
}

#what_is {
clear: both;
margin-top: 12px;
padding: 8px;
border: 4px solid #ddffdd;
background-color: #f6fcf6;
color: #111;
height: 191px;
}

h4 {
font-size: 18px;
margin: 8px 0px 5px 0;
padding: 0;
}

#screenshot {
float: left;
width: 280px;
}

#channel_list h3 {
color: #d00;
font-size: 18px;
border-bottom: none;
width: 230px;
float: left;
}

#channels {
float: right;
width: 500px;
padding-top: 3px;
}

.button {
width: 320px;
float: left;
padding-bottom: 15px;
padding-top: 5px;

}

</style>

	
</head>

<body onLoad="saveOriginalButtonsHTML();">

<!--CONTAINER-->
<div id="container">

<!--HEADER-->
	<div id="header">
	
	<!--LOGO-->
	<div id="logo">
		<h1><a href="http://getdemocracy.com"><span></span>Democracy: Internet TV</a></h1>
	</div>
	<!--/LOGO-->	
	
	<!--NAV-->
	<div id="nav">
		<ul>
			<li><a href="http://getdemocracy.com/help">Help</a></li>
			<li><a href="http://getdemocracy.com/downloads">Downloads</a></li>
			<li><a href="http://getdemocracy.com/donate">Donate</a></li>

			<li><a href="http://getdemocracy.com/about">About</a></li>
			<li><a href="http://getdemocracy.com/news">Blog</a><a href="http://getdemocracy.com/news/feed" class="feed">&nbsp;</a></li>		
		</ul>
	</div>
	<!--/NAV-->
	
	<!--USERNAV-->		
	<div id="usernav">
		<ul>
			<li id="usernav-watch"><a href="http://getdemocracy.com/watch"></a></li>
			<li id="usernav-make"><a href="http://getdemocracy.com/make"></a></li>
			<li id="usernav-code"><a style="margin-right: 0;" href="http://getdemocracy.com/code"></a></li>
		</ul>
	</div>
	<!--/USERNAV-->
	
</div>	<!--/HEADER-->	


	<!--CONTENT BLOCK-->
  <div class="content" style="padding:0px;">
	



<Br />
<h4>Democracy 1-Click Subscribe Button Maker</h4>

<p>
Create buttons or a text link to subscribe your users to your video RSS feeds. 
</p>

<p>
Our 1-Click Subscribe system goes beyond typical subscribe buttons in two key ways:
<ul>
<li>
<strong>You can make a button for a single RSS feed or multiple feeds.</strong>  If you publish multiple video feeds, or if you want to recommend a bunch of feeds that you like, you can subscribe people to a whole batch of feeds in one fell swoop.
</li>
<li>
<strong>If a Windows user doesn't have Democracy Player installed, they can download the software with your channels pre-subscribed.</strong>  It's like your own branded version of the player that comes with your content. (We don't have the pre-subscribed installer available for Mac or Linux yet, but the subscribe buttons work for people who have the player installed and when they click on the button, they will get a link to download the application if they don't have it already.)
</li>
</ul>

<Br />
<p><strong>Step 1. Paste in the URLs of your video RSS feeds, one per line.</strong><Br />
<textarea cols="45" id="urls" name="urls" rows="5"></textarea>
<br /><br />
<input name="commit" type="submit" value="Make My Buttons &gt;&gt;" onClick="generateButtons(); return false;"/>
</p>

<div id="generated_buttons" style="display: none;">

  <p><strong>Step 2. Pick the button you want to use and paste the code into your site.</strong></p>

  <p>Subscribe URL: <span id="subscription_url_link"></span></p>

  <div id="buttons">

  </div>

</div>


	<!--FOOTER-->
	<div id="footer">
	
	<ul id="footernav">
	
		
			<li>
			<a href="http://getdemocracy.com/watch">Watch TV</a>
			<ul>
				<li><a href="http://getdemocracy.com/downloads">Download Player</a></li>
				<li><a href="http://getdemocracy.com/walkthrough">Screenshots</a></li>
				<li><a href="http://getdemocracy.com/walkthrough">Walkthrough</a></li>
			</ul>
		</li>	
	
	
				<li><a href="http://getdemocracy.com/make">Make TV</a>
			<ul>
				<li><a href="http://www.getdemocracy.com/help/faq/index.php#05-02">FAQ - Channel Possibilities</a></li>				
				<li><a href="http://getdemocracy.com/broadcast">Broadcast Machine</a></li>
				<li><a href="http://getdemocracy.com/make/channel-guide">Make a Channel</a></li>
				<li><a href="http://channelguide.participatoryculture.org">Channel Guide</a></li>
				<li><a href="http://getdemocracy.com/make/channel_examples.php">Examples of channels</a></li>
			</ul>
		</li>	
	
		
		
			<li><a href="http://getdemocracy.com/code">Code</a>
			<ul>
			
			<li><a href="http://develop.participatoryculture.org/">Developer Center</a></li>
				<li><a href="https://develop.participatoryculture.org/projects/dtv/browser/trunk/tv/">Source Code</a></li>
				<li><a href="https://develop.participatoryculture.org/projects/dtv/report">Bug Tracker</a></li>
				<!-- <li><a href="http://getdemocracy.com/">Mailing Lists</a></li> -->
			</ul>
		</li>		
			
			
						
		<li><a href="http://getdemocracy.com/help/">Help and Forums</a>
			<ul>
				<!--<li><a href="http://getdemocracy.com/help">Viewer Help</a></li> -->
				<li><a href="http://getdemocracy.com/help/faq#viewers">Viewer FAQ</a></li>
				<!--<li><a href="http://getdemocracy.com/help">Creator Help</a></li> -->
				<li><a href="http://getdemocracy.com/help/faq#creators">Creator FAQ</a></li>
				<li><a href="http://forum.getdemocracy.com/">Discussion Forums</a></li>
			</ul>
		</li>	
		
	
				
							<li><a href="http://getdemocracy.com/about">About the Platform</a>
			<ul>
				<li><a href="http://getdemocracy.com/news">News / Blog</a></li>
				<li><a href="http://getdemocracy.com/press">Press</a></li>
				<li><a href="http://getdemocracy.com/contact">Contact</a></li>
				<li><a href="http://getdemocracy.com/store">Store</a></li>
				<li><a href="http://getdemocracy.com/jobs">Jobs</a></li>
				<li><a href="https://secure.democracyinaction.org/dia/organizations/pcf/shop/custom.jsp?donate_page_KEY=1283&t=Democracy.dwt">Donate</a></li>
			</ul>
		</li>		
		



	</ul>
	
	<div id="footer-meta">
		<p>The Democracy platform is a project of the <a href="http://www.participatoryculture.org">Participatory Culture Foundation</a><p>
	</div>
	
	</div>

</div>
</div> <!-- close container -->


</body>
