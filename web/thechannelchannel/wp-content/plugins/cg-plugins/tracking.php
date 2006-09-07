<?php

if (!isset($user_level) && function_exists('get_currentuserinfo'))
	get_currentuserinfo(); // cache away in case hasn't been yet...
	
$trkAbsPath = dirname(__FILE__).'/';
	
// locate the wp path...
$conoff = strpos($trkAbsPath, 'wp-content');
$rootPath = substr($trkAbsPath, 0, $conoff);

require_once($trkAbsPath.'error-handler.php');

require_once($rootPath.'wp-config.php');
// since this is a custom chaitgear-only thing at the moment, not meta-data based yet, needs my-setup too...
require_once($rootPath.'my-setup.php');


$showStats = 0;
if (isset($_GET['stats']))
{
	$showStats = $_GET['stats'];
	$showStats = intval($showStats);
}

function track_postview($postID, $page=1)
{
	global $wpdb, $tableposts, $user_level, $isaSearchbot;
	global $weCameFromAnotherSite, $wasPrimaryAdminIP;
	
	if ($isaSearchbot) return;
	if ($user_level > 4) return; // so primary admins don't increase counts!
	if ($wasPrimaryAdminIP) return;
	if ($page>1)
	{
		if ($weCameFromAnotherSite)
			return; // don't count if coming from internal page.
	}

	$uquery = "UPDATE $tableposts SET post_viewcount=post_viewcount+1 where ID=$postID";
	$wpdb->query($uquery);
}


function pop_posts_list($max=6, $randomize=3, $minMax=0, $showViewCount=false, $showInline=false, $showHeat=true)
{
	global $wpdb, $tableposts;
	global $siteurl, $blogfilename;
	
	$output = '';

	if ($randomize>$max) $randomize = $max;
	$extrap = 0;
	if ($randomize) $extrap = 3 + 2 * (1 + $max - $randomize);
	$totalp = $max + $extrap;
	if ($totalp<$minMax) $totalp = $minMax;

	$rquery = "SELECT ID, post_title, post_date, post_viewcount FROM $tableposts";
	$rquery .= " WHERE (post_status='publish' || post_status='sticky')";
	$rquery .= " AND post_type!=1"; // General
	$rquery .= " AND post_type!=11"; // Files
	$rquery .= " AND post_type!=12"; // Linked
	$rquery .= " AND post_type!=13"; // Category
	$rquery .= " AND post_type!=14"; // About
	$rquery .= " ORDER BY post_viewcount DESC LIMIT $totalp";
	$results = db_getresults($rquery, OBJECT, "pop_posts_list_$totalp");

	$c = count($results); 	
	if ($c<=0) return '<ul><li>No posts returned.</li></ul>';

	if ($c<=$max) $randomize = 0;
	
//	dbglog("total post count = $c");
	
	$usepost = array_fill(0, $c, false); // to initialize the array -- removes error notices...
	for ($i=0; $i<($max-$randomize); $i++)
		$usepost[$i] = true;
	$k = $i;
	if ($randomize)
	{
		for ($i=$k; $i<$max; $i++)
		{
			$apick = rand($k, $totalp-1);
			if ($usepost[$apick]) // already taken.  start from top and grab one.
			{
				for ($c=$k; $c<$max; $c++)
				{
					$apick = $c;
					if (!$usepost[$apick]) break;
				}
			}
			$usepost[$apick] = true;
		}
	}
	
	$output .= '<ul>';
	$i = 0;
	foreach ($results as $result)
	{
		if ($usepost[$i])
		{
//dbg_log("postData = ".serialize($result));
			$postID = $result->ID;
			$post_title = stripslashes($result->post_title);
			$viewcnt = $result->post_viewcount;
			$output .= '<li>';
//dbg_log(' = '.$theHeat);
			$theHeat = get_heat_index($result);
			if ($showHeat)
				if ($theHeat>=1) $output .= "<img class='heat' src='$siteurl/images/hot-flame-small.gif' alt='[HOT] ' />";
							
			if ($showViewCount && $showInline)
				$output .= '('.$viewcnt.') @ '.sprintf("%01.2f",$theHeat).' ';
			$output .= '<a href="'.get_permalink($postID).'"';
			if ($showViewCount)
			{
				$output .= ' title="Viewed '.$viewcnt.' times, Heat = ';
				$output .= sprintf("%01.2f",$theHeat);
				$output .= '"';
			}
			else
				$output .= ' title="'.$post_title.'"';
			$output .= '>'.$post_title.'</a>';
			$output .= '</li>';
		}
		$i++;
	}
	$output .= '</ul>';
	
	return($output);
}


function the_viewcount()
{
	global $post;
	if (empty($post)) return 0;
	return intval($post->post_viewcount);
}

if (!empty($showStats))
{
	if ($user_level>=2)
	{
		echo '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">';
		echo '<html xmlns="http://www.w3.org/1999/xhtml">';
		//else if ($showStats)
			echo '<title>Showing popular posts by pageload statistics</title>';
		echo '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />';
		echo '<style media="screen" type="text/css">';
		echo '	body {';
		echo '		font: 12px Georgia, "Times New Roman", Times, serif;';
		echo '		margin-left: 5%;';
		echo '		margin-right: 5%;';
		echo '	}';
		echo '	span {';
		echo '		font: bold 12px Arial, sans-serif;';
		echo '	}';
		echo '</style>';
		echo '</head><body><br>';
		
			$count = 100;
			if ($showStats)
				$count = $showStats;
			echo pop_posts_list($count, 0, 0, true, true, false);
			
		echo '</body>';
		echo '</html>';
	}
}
	
?>