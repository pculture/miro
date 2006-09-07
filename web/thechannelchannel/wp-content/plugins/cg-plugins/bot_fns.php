<?php

$botfnsPath = dirname(__FILE__).'/';
require_once($botfnsPath."helper_fns.php");

function isa_bot($userAgent)
{
		// check for bots...
		// http://www.netsys.com/cgi-bin/display_article.cgi?1193 is a good source.
		// http://www.psychedelix.com/agents2.html is also.
		$ignoreBots = array(
				// screw it.  catch anything with 'bot' in the name..
//				'bot',
//				'Bot',
				// a new catch-all for "ZZZbot.htmX" strings
				"bot.htm",
				//newest
				"BecomeBot",
				"blogsnowbot", //blogsnow.com
				"BTBot", //btbot.com
				"CipinetBot", //cipinet.com
				"EasyDL", // keywen.com
				"egothor", // xdefine.org
				"Gaisbot",
				"Jetbot",
				"iKnowWhoYouAreBot", // blogshares
				"Mediapartners-Google",
				"mozDex", // mozdex.com
				"Girafabot", // sidebar thingy for browser
				"NPBot", // nameprotect.com
				"ObjectsSearch", // 
				"OpenBot", //openfind.com.tw
				"psbot", //picsearch.com
				"timboBot", //breakingblogs.com
				//prev
				"GeoURLBot", //www.geourl.org
				"BlogShares Bot", //www.blogshares.com, crawls weblogs.com changes
				"Gigabot", // www.gigablast.com search bot
				"msnbot", // MSN beta search bot
				"NaverBot", // The bot for NHN Corp - which runs a successful Korean search engine at Naver.com.
				"obidos-bot", // http://www.onfocus.com/bookwatch/, crawls weblogs.com changes looking for amazon books.
				"Technoratibot", //
				"SurveyBot", //
				"Freshbot", // supposedly google, though I'VE never seen it!
				"Googlebot",
				"Blogosphere", //
				"BlogPulse", //http://www.blogpulse.com/ tracks key phrase occurrance in blogs
				"BravoBrian", // these next three come together, broken out just in case.  BravoBrian is for bStop, some parental filtering thing, crawls.
				"SpiderEngine", // #2
				"MarcoPolo", // #3
				"CrawlConvera", //  	Convera is billed as "Enterprise Search and Categorization Solutions". No information page is available. Email: CrawlConvera@yahoo.com
				"FyberSpider", // www.fybersearch.com
				"Jakarta Commons-HTTPClient", // not sure what this is for/from -- could be anything.
				"libwww-perl", // associated with numerous robots...
				"libwww-FM", // associated with a web SEO helper engine...
				"Marvin", // Marvin Medhunt robot, http://www.hon.ch/MedHunt/Marvin.html
				"NITLE Blog Spider", // experimental
				"NG/", // ????
				"Sqworm", // robot used by numerous locations, AOL, TimeWarner, others.  also Used for Corporate web security to prevent internal internet hacking and misuse. 
						// SQWORM is ALSO used by websense.com, a corporate security checker, to look through what corporate users are browsing.
				"WEP Search", // spambot.
				"Space Bison", // some web filtering thing.
				"Waypath Scout", // bot tracking weblogs changes
				"Enter new UA", // a string that shouldn't be there...
				"The World as a Blog", // bot that watches weblogs.com for changes, shows users at brainfoff.com/geoblog a world map and recent blogging activity.
				"Poodle predictor", // a SEO helper bot.
				"GetRight", // download agent.
				"Python-urllib", //possibly google.
				"ping.blo.gs", // blo.gs pinging us back.
				"Java/", //???????????
				"Butch__", //?????????
				"Wget/", //?????????
				"TeomaAgent",
				"Zyborg",
				"Gulliver",
				"Architext spider",
				"FAST-WebCrawler",
				"slurp", // Inktomi's spider which gives data to Microsoft and Hotbot search engines. Inktomi is owned by Yahoo but does not index for that search engine yet. 
				"Ask Jeeves",
				"ia_archiver",
				"Scooter",
				"Mercator",
				"crawler@fast",
				"Crawler",
				"InfoSeek sidewinder",
				"Lycos_Spider_(T-Rex)",
				"Fluffy the Spider",
				"Ultraseek",
				"MantraAgent",
				"Moget",
				"T-H-U-N-D-E-R-S-T-O-N-E",
				"MuscatFerret",
				"VoilaBot",
				"Sleek Spider",
				"KIT_Fireball",
				"WebCrawler",
				// catch alls?
				// Spider
				// Crawler
			);
				
		if (findstr($userAgent, $ignoreBots))
			return(true);
		if (strlen($userAgent)<4) // punt too.  !!NOTE!! this will also catch NULL/EMPTY userAgent strings.
			return(true);
		// if no slash and no parens, let's assume it's a bot.
		if (FALSE===strpos($userAgent, '/')
		&&	FALSE===strpos($userAgent, '(')
			)
			return(true);
			
		return(false);
}

$isaSearchbot = isa_bot($_SERVER["HTTP_USER_AGENT"]);
if (0) // turn to 1 to test bot output of site.
	$isaSearchbot = true;
if ($doing_rss)
	$isaSearchbot = false; // don't flag as bot.  this will increase referral counts, possibly read counts.
?>