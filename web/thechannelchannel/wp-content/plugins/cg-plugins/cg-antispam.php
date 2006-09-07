<?php
//cg-antispam.php


$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);

$antiPath = dirname(__FILE__).'/';
require_once($antiPath.'helper_fns.php');
require_once($antiPath.'db_fns.php');
// bring in the cg-referrer blacklist
require_once($antiPath.'cg-blacklist.php');

$cgas_options['puntspam'] = false; // by default false: save all spam to db, just in case, or for future post-processing.
$cgas_options['checkip'] = false;
$cgas_options['checkname'] = true;
$cgas_options['checkagent'] = true;
$cgas_options['checkblack'] = true;
$cgas_options['checklinks'] = true;
$cgas_options['max_links'] = 4;
$cgas_options['checktime'] = 20; // seconds between posts of matching IP|URL

function checkCommentBlacklist($approved, $userIP, $userName, $userAgent, $comment, $commentURL, $comment_post_ID, $comment_type, $comment_date)
{
	global $cgas_options;
	global $ignoreReferSites, $ignoreAgents, $ignoreSpammerIPs;
	global $tableposts;
	
//	die("QUICK SANITY CHECK OF CHECKCOMMENTBLACKLIST:<br/>$userIP<br/>$userAgent<br/>$comment<br/>$commentURL");	
	// first, make sure we're coming from the right referring page.
/*
	if ($testref)
	{
		$ref = getenv('HTTP_REFERER');
		if (!findstr($ref, 'wp-comments-popup.php'))
			return(true); // didn't come from the right place!
	}
*/

	// TBD, can do specific sanity-checking of not-yet-approved trackback/pingback, such as checking for a valid referring page, and that page having a fwd ref to us...
	if (!$approved)
	{
	}
	
	if ($cgas_options['checkname'])
	{
		$safeName = safeunhtmlentities($userName);
		if ($safeName!=$userName)			
			return("cg-html-username[$userName]");
		if ($match = findstr($safeName, $ignoreReferSites)) // name
		{
			die("blacklisted username [$match]");	
			return("cg-blacklist-username[$match]");
		}
	}

	if ($cgas_options['checkagent'])
	{
		if (empty($userAgent) && empty($comment_type)) // normal comments should have a UA.
			return("cg-blank-ua");
		if ($match = findstr($userAgent, $ignoreAgents))
		{
//			die("blacklisted UA [$userAgent]");	
			return("cg-blacklist-ua[$match]");
		}
	}

	// make a smooshed string with all data.
	$smoosh = $userURL.' '.$comment; // space ensures not back-to-back urls.
	// should pre-process the comment content to unhtml it.  this will make it so spammers can't encode strings/urls using html escaped characters...
	$smoosh = safeunhtmlentities($smoosh);
	$httpCount = preg_match_all("/http:\/\/[\S]+/i", $smoosh, $httpLinks);
	$arefCount = preg_match_all("/<a href=[^>]+>/i", $smoosh, $arefLinks);

	$allLinks = '';
	if ($httpCount) $allLinks .= implode(' ', $httpLinks[0]).' ';
	if ($arefCount) $allLinks .= implode(' ', $arefLinks[0]).' ';

	// this is a useful debug line to test what's coming through in a given comment...
	//if (!empty($allLinks)) die($httpCount.'=='.serialize($httpLinks).'<br/>'.$arefCount.'=='.serialize($arefLinks).'<br/>'.$allLinks.'<br/>'.$smoosh);
	
	// test against referer_blacklist...
	if ($cgas_options['checkblack'])
	{
		// this is TOO RESTRICTIVE.
/*
		if ($match = findstr($smoosh, $ignoreReferSites))
		{
//			die("blacklisted word [$match] in:<br/><quote>$smoosh</quote>");
			return("cg-blacklist-word  [<b>$match</b>]");
		}
*/
		// INSTEAD, let's try just comparing against any urls.
		if ($match = findstr($allLinks, $ignoreReferSites))
		{
//			die("blacklisted word [$match] in:<br/><quote>$smoosh</quote>");
			return("cg-blacklist-link [<span style='color: #FF5555;  font-weight: bold;'>$match</span>]");
		}		
		// COULD ADD REFERRER TEST, though less useful due to trackback/pingbacks not coming from us...
	}
	
	if ($cgas_options['checkip'])
		if ($match = findstr($userIP, $ignoreSpammerIPs))
		{
//			die("blacklisted IP [$match]");
			return("cg-blacklist-ip [<span style='color: #FF5555;  font-weight: bold;'>$match</span>]");
		}
	
	if (1)
	{
		// look for 2+ '-' characters in the domain name of all URLs.  That's a kicker.
	}
	
	// look for more than 4 links total (this function gets the URL field tacked on...)
	if ($cgas_options['checklinks'])
	{
		// look for two links back to back
		$num = preg_match("/(<\/a><a href=)/i", $comment, $matches); // catch back to back link spamming!!!
		if ($num)
		{
			//die("bad links [".htmlentities($matches[0])."]");
			return('cg-adjoininglinks');
		}
		
		// look for too many links total.
		$max = $cgas_options['max_links'];
		if ($httpCount > $max || $arefCount > $max) //nail it.
			return("cg-toomanylinks [<span style='color: #FF5555;  font-weight: bold;'>$httpCount|$arefCount</span>]");
	}
		
// since these are DB lookups, save for last...
	
	// test a valid field in the database for the given post...
	$apost = db_getrow("SELECT post_date FROM $tableposts WHERE ID='$comment_post_ID'", OBJECT, 0, "postexists");
	if (empty($apost)) // bad post, BAD post. ;)
		return('cg-postnotexist');

		
	if ($cgas_options['checktime'])
	if (!$approved && $comment_date && $userIP)
	{
		$userURLCheck = '';
		if ($userURL)
			$userURLCheck = "OR comment_author_url = '$userURL'";
		$timelast = db_getrow("SELECT comment_date FROM $tablecomments WHERE comment_approved = '0' AND comment_date < '$comment_date' AND comment_ID != '$commID' AND (comment_author_IP = '$userIP' $userURLCheck) ORDER BY comment_date DESC LIMIT 1", OBJECT, 0);
		if ($timelast)
		{
			$time_lastcomment= mysql2date('U', $timelast->comment_date);
			$time_newcomment= mysql2date('U', $comment_date);
			if (abs($time_newcomment - $time_lastcomment) < 20)  // 20s between posts or it goes into moderation as spam...
				return("bl-toofast");
		}
	}	
	
	//die("okay");
	return(null);
}

// global we set if we're allowing save-to-db-on-bl
$blackListComment = 0;

function cgas_approve_comment($approve)
{
	global $blackListComment;
	//die ("checking approval: $blackListComment");	
	if ($blackListComment) // we set a string.  else zero, we didn't touch...
		$approve = 'spam'; //$blackListComment is what we want, but they used a FREAKING ENUM!!!	
	return ($approve);
}


function cgas_screen_comment($commentdata)
{
	global $blackListComment;
	global $cgas_options;
	
   	$userAgent = $_SERVER['HTTP_USER_AGENT'];
	$userIP = $_SERVER['REMOTE_ADDR'];
	$userRef = $_SERVER['HTTP_REFERER'];
	
	// then break out the comment datablock
	extract($commentdata);
	//$comment_content
	//$comment_type
	//$comment_post_ID
	//$comment_author
	//$comment_author_email
	//$comment_author_url
	
	if ($blackListComment = checkCommentBlacklist(0, $userIP, $comment_author, $userAgent, $comment_content, $comment_author_url, $comment_post_ID, $comment_type))
	{
		//die("caught a ".$blackListComment);
		if ($cgas_options['puntspam'])
			die('Sorry, comment system is down temporarily.');
	}
		
/*
	if (empty($comment_author) && !empty($comment_author_email)) // no real user would give email but not name
	{
		$blackListComment = 'no-name';
		die('Sorry, comment system is down temporarily.');
	}
	
	if (empty($comment_author) || FALSE!==strpos($comment_author, '&#')) //bad chars for a name, or no name
		$blackListComment = 'bad-name';
*/

	// other possible checks
	// the require-initial-caps-on-names thing

	//die ($blackListComment);	
	
	return($commentdata);
}


if ( strstr($_SERVER['REQUEST_URI'], 'cg-plugins/cg-antispam.php') ) // under cg plugins
{
	//==================================================
	//==================================================
	if (!function_exists('add_magic_quotes'))
	{
		function add_magic_quotes($array)
		{
			foreach ($array as $k => $v) {
				if (is_array($v)) {
					$array[$k] = add_magic_quotes($v);
				} else {
					$array[$k] = addslashes($v);
				}
			}
			return $array;
		} 
	}
	
	if (!get_magic_quotes_gpc())
	{
		$_GET    = add_magic_quotes($_GET);
		$_POST   = add_magic_quotes($_POST);
		$_COOKIE = add_magic_quotes($_COOKIE);
	}
	
	$findvars = array('action', 'tag', 'show', 'flush', 'page', 'options');
	
	for ($i=0; $i<count($findvars); $i += 1)
	{
		$avar = $findvars[$i];
		if (isset($$avar)) continue;
		if (!empty($_POST[$avar]))
			$$avar = $_POST[$avar];
		elseif (!empty($_GET[$avar]))
			$$avar = $_GET[$avar];
		else
			$$avar = '';
	}
	
	if ($action=='create')
	{
		echo "CG-AntiSpam installing...";
//		$showingErrors = $wpdb->show_errors;
//		$wpdb->hide_errors();
//		install_related_table();
		echo '<br/><a href="'.$_SERVER['HTTP_REFERER'].'">Return Back</a>';
//		if ($showingErrors) $wpdb->show_errors();
	}
	else
	if ($action=='tag')
	{ // go through ALL comments, tag those that don't pass the screen_comment stuff.
		$qids = db_getresults("SELECT comment_ID FROM $tablecomments WHERE comment_approved!='spam'", OBJECT, "find comments");
		?>
			<div class="wrap">
				<h2>Tagging Spam Comments:</h2>
				<?php
					//echo serialize($qids);
					$spamCount=0;
					if (empty($qids))
						echo "<p>No comments.</p>";
					else
					{
						foreach($qids as $cid)
						{
							if ($cid->comment_ID==1) continue; // skip the initial 'welcome' comment...
							
							// start by showing them on screen if they hit...
							$comm = db_getrow("SELECT * FROM $tablecomments WHERE comment_ID='".$cid->comment_ID."'", OBJECT, 0, "one comment");
							//echo serialize($qresults).'<br/>';
							if (!empty($comm))
							{
//								$comm = &$qresults[0];
								if ($blackListComment = checkCommentBlacklist($comm->comment_approved, $comm->comment_author_IP, $comm->comment_author, $comm->comment_agent, $comm->comment_content, $comm->comment_author_url, $comm->comment_post_ID))
								{
									echo "<p>Comment #".$cid->comment_ID.": tagged as $blackListComment</p>";
									db_runquery("UPDATE $tablecomments SET comment_approved='spam' WHERE comment_ID='".$cid->comment_ID."'", OBJECT, "admin - spam tagging");
									$spamCount++;
								}
							}
						}
						echo "<p>Done.  (Spam comments found = $spamCount.)</p>";
					}
				?>
			</div>
		<?php
	}
	else
	if ($action=='show')
	{ // show all comments that don't have approved==0|1
		$qresults = db_getresults("SELECT * FROM $tablecomments WHERE comment_approved='spam'  ORDER BY comment_ID  LIMIT 100", OBJECT, "show spam comments");
		?>
			<div class="wrap">
				<h2>Showing Spam Comments (first 100):</h2>
				<table>
				<?php
					if (empty($qresults))
					{
						echo "<p>No comments have been marked as spam yet.  Try 'Tag'.</p>";
					}
					else
					{
						echo "<tr><th>ID</th><th>tag</th><th>who</th><th width=50%>comment</th></tr>";
						foreach($qresults as $comm)
						{
							$tag = 'wp-spam';
							if ($blackListComment = checkCommentBlacklist($comm->comment_approved, $comm->comment_author_IP, $comm->comment_author, $comm->comment_agent, $comm->comment_content, $comm->comment_author_url, $comm->comment_post_ID))
								$tag = $blackListComment;
							echo '<tr valign="top">';
								echo '<td>'.$comm->comment_ID.'</td>';
								echo '<td>'.$tag.'</td>';
								echo '<td>'.$comm->comment_author.'</td>';
								echo '<td>'.$comm->comment_content.'</td>';
							echo '</tr>';
						}
//	(comment_post_ID, comment_author, comment_author_email, comment_author_url, comment_author_IP, comment_date, comment_date_gmt, comment_content, comment_approved, comment_agent, comment_type, user_id)
					}
				?>
				</table>
			</div>
		<?php
	}
	else
	if ($action=='flush')
	{ // go through and delete all comments that don't have approved==0|1
		$qids = db_getresults("SELECT comment_ID FROM $tablecomments WHERE comment_approved='spam' ORDER BY comment_ID", OBJECT, "flush spam comments");
		?>
			<div class="wrap">
				<h2>Flushing Spam Comments:</h2>
				<?php
					//echo serialize($qids);
					$spamCount=0;
					if (empty($qids))
						echo "<p>No comments.</p>";
					else
					{
						foreach($qids as $cid)
						{
							// start by showing them on screen if they hit...
							$qresults = db_getresults("SELECT * FROM $tablecomments WHERE comment_ID='".$cid->comment_ID."'", OBJECT, "one comment");
							//echo serialize($qresults).'<br/>';
							if (!empty($qresults))
							{
								$comm = &$qresults[0];
								if ($blackListComment = checkCommentBlacklist($comm->comment_approved, $comm->comment_author_IP, $comm->comment_author, $comm->comment_agent, $comm->comment_content, $comm->comment_author_url, $comm->comment_post_ID))
								{
									echo "<p>Comment #".$cid->comment_ID.": tagged as $blackListComment</p>";
									db_runquery("DELETE FROM $tablecomments WHERE comment_ID='".$cid->comment_ID."'", OBJECT, "admin - delete spam comment");
									$spamCount++;
								}
							}
						}
						echo "<p>Done.  (Spam comments found = $spamCount.)</p>";
					}
				?>
			</div>
		<?php
	}
	else
	{
		?>
			<div class="wrap">
				<h2>CG-AntiSpam</h2>
				<p>Ready.</p>
				<?php
					$qcount = db_getresults("SELECT count(*) as num FROM $tablecomments WHERE comment_approved='spam' ORDER BY comment_ID", OBJECT, "count spam comments");
					if (!empty($qcount)) $qcount = $qcount->num;
					echo "<p>Total comments marked as spam = ".intval($qcount).".</p>";
				?>				
				<h3>Checking for:</h3>
				<ul>
					<li>Recording Spam in DB: <?php echo $cgas_options['puntspam']?'[NO]':'[yes]'; ?></li>
					<li>Blacklisted Spam IPs: <?php echo $cgas_options['checkip']?'[ON]':'[off]'; ?></li>
					<li>Blacklist Words/Domains: <?php echo $cgas_options['checkblack']?'[ON]':'[off]'; ?></li>
					<li>Spamming User Agents: <?php echo $cgas_options['checkagent']?'[ON]':'[off]'; ?></li>
					<li>Validate User Name: <?php echo $cgas_options['checkname']?'[ON]':'[off]'; ?></li>
					<li>Back-to-back Links: <?php echo $cgas_options['checklinks']?'[ON]':'[off]'; ?></li>
					<li>Too-Rapid Posting: <?php echo $cgas_options['checktime']?('[ON, <'.$cgas_options['checktime'].'s]'):'[off]'; ?></li>
					<li>Valid Post ID: [ON]</li>
					<li>Max <?php echo $cgas_options['max_links'];?> Links Total: <?php echo $cgas_options['checklinks']?'[ON]':'[off]'; ?></li>
				</ul>
			</div>
		<?php	
	}
}


?>