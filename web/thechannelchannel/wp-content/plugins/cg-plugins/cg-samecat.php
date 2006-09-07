<?php

/* CG-SameCat implementation */

// until WP does an srand call ALWAYS, we need it here.
srand((double) microtime() * 1000000);

$scPathBase = dirname(__FILE__).'/';
require_once($scPathBase.'helper_fns.php');

$sameCatDebug = false;
$sameCatDebugout = '';

function posts_of_cat($cats, $limitcount = 8, $not_post = 0, $orderby = 'date', $inFuture=false, $showExcerpts=false)
{
	global $tableposts, $tablepost2cat, $wpdb;
	global $sameCatDebug, $sameCatDebugout;

	$eq = '=';
	$andor = 'OR';
  $whichcat = ' AND (category_id '.$eq.' ';
  if (strpos($cats, ','))
  {
		if ($sameCatDebug) $sameCatDebugout .= "[Comma separated list] ";
	  $catarr = explode(',', $cats);
	  $whichcat .= intval($catarr[0]);
	  for ($i = 1; $i < (count($catarr)); $i = $i + 1)
	      $whichcat .= ' '.$andor.' category_id '.$eq.' '.intval($catarr[$i]);
  }
  else
  if (is_array($cats))
  {
	  $whichcat .= intval($cats[0]->cat_ID);
	  for ($i = 1; $i < (count($cats)); $i = $i + 1)
	      $whichcat .= ' '.$andor.' category_id '.$eq.' '.intval($cats[$i]->cat_ID);
	}
  else $whichcat .= intval($cats); // just an integer anyway...
  $whichcat .= ')';

//	if ($sameCatDebug) $sameCatDebugout .= "posts cats = [$cats][$whichcat]<br />";
//  $what = "DISTINCT *"; // for ALL post data for every post in the cat.  This could be HUGE.
  $what = "DISTINCT ID, post_title, post_name, post_status, post_date"; // for just basic data for links
  if ($showExcerpts)
  	$what .= ", post_excerpt";
  if (empty($orderby))
  	$orderby = "post_status DESC, post_date DESC";
  else
  {
	  if ($orderby=='title')
		  $orderby = "post_status DESC, post_$orderby ASC";
		else
		  $orderby = "post_status DESC, post_$orderby DESC";
	}

	$wherefuture = '';
	if (!$inFuture)
	{
		$time_difference = get_settings('time_difference');
		$now = date('Y-m-d H:i:s',(time() + ($time_difference * 3600)));
		$wherefuture = "AND post_date <= '$now'";
	}
	
 	$query = "
						SELECT $what
						FROM $tableposts
						LEFT JOIN $tablepost2cat ON ($tableposts.ID = $tablepost2cat.post_id)
						WHERE 1=1 $whichcat
							AND (post_status = 'publish' || post_status = 'sticky')
							AND ID != $not_post
							$wherefuture
						ORDER BY $orderby
						LIMIT $limitcount";
	$catposts = $wpdb->get_results($query, OBJECT, "posts_of_cat");
		if ($sameCatDebug) $sameCatDebugout .= "[QUERY:] ".$query;
	if ($sameCatDebug) $sameCatDebugout .= "posts results = ".serialize($catposts)."<br />";
	return($catposts);
}

function list_posts_of_cat($cats='current', $max = 5, $randomize = 0, $not_post = 0, $orderby='date', $doecho=0, $format='html', $before = "", $after = "", $inFuture=false, $showExcerpts=false)
{
	global $sameCatDebug, $sameCatDebugout;
	global $post;
	
	if (is_single()) $not_post = $post->ID;
	if ($cats=='current') $cats = get_the_category();

	$emptystr = "<li>No matching posts.</li>";
	// I built this random system as a differentiation from array_rand, as it wasn't doing quite what I wanted.
	if ($randomize>$max) $randomize = $max;
	$extrap = 0;
	if ($randomize) $extrap = 3 + 2 * (1 + $max - $randomize);
	$totalp = $max + $extrap;

	if ($sameCatDebug) $sameCatDebugout .= "<br /><br /><b>DEBUGGING same_cat:</b> ".($randomize?"asked for random [$randomize]":"in order")."<br />maximum posts = $totalp";

	$catposts = posts_of_cat($cats, $totalp, $not_post, $orderby, $inFuture, $showExcerpts);
	
	$c = count($catposts); 	
	if ($sameCatDebug) $sameCatDebugout .= ", total query posts = $c";
	if ($c<=0) return "<ul>$emptystr</ul>";

	if ($c<=$max)
	{
		$randomize = 0;
		if ($sameCatDebug) $sameCatDebugout .= ", <B>randomize disabled - too few posts</b><br />";
	}
	else
		if ($sameCatDebug) $sameCatDebugout .= "<br />";
	
	$usepost = array_fill(0, $c, false); // to initialize the array -- removes error notices...
	for ($i=0; $i<($max-$randomize); $i++)
		$usepost[$i] = true;
	$k = $i;
	if ($sameCatDebug && $randomize)
	{
		if ($k) $sameCatDebugout .= ", end pre-fill index = $k<br />";
		else $sameCatDebugout .= ", no pre-fill<br />";
	}

	if ($randomize)
	{
		for ($i=$k; $i<$max; $i++)
		{
			$apick = rand($k, $c-1);
			if ($sameCatDebug) $sameCatDebugout .= "random pick = $apick<br />";
			if ($usepost[$apick]) // already taken.  start from top and grab one.
			{
				if ($sameCatDebug) $sameCatDebugout .= "slot $apick already taken<br />";
				for ($c=$k; $c<$max; $c++)
				{
					$apick = $c;
					if (!$usepost[$apick]) break;
					if ($sameCatDebug) $sameCatDebugout .= "slot $apick already taken<br />";
				}
			}

			if ($sameCatDebug) $sameCatDebugout .= "slot $apick available<br />";
			$usepost[$apick] = true;
		}
	}

	$output = '';
	$i = 0;
	foreach ($catposts as $apost)
	{
		if (!$usepost[$i++]) continue;
		
		if (0) // simple output
		{
			$output .= '<li>';
			$output .= $apost->post_title;
			$output .= '</li>';
		}
		else
		{ // copied from get_archives
      if ($apost->post_date != '0000-00-00 00:00:00')
      {
          $url  = get_permalink($apost->ID, $apost);
          $arc_title = stripslashes($apost->post_title);
          if ($arc_title)
          	$text = strip_tags($arc_title);
          else
            $text = $apost->ID;        
          $output .= get_archives_link($url, $text, $format, $before, $after);
          if ($showExcerpts)
	          $output .= "<br/><span>".stripslashes($apost->post_excerpt)."</span>";
      }
		}
	}
	if (empty($output))
		$output = "<li>No matching posts.</li>";
	// add pre/post tags.
	$output = '<ul>'.$output;
	$output .= '</ul>';

	if ($doecho)
		echo $output;
	return $output;
}
?>