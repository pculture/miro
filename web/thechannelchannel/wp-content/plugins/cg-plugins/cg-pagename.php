<?php

		
$pnPathBase = dirname(__FILE__).'/';

// locate the wp path...
if (FALSE===strpos($pnPathBase, 'wp-content')) // plugin
	$pnPathPrefix = $pnPathBase.'../'; // cgplugins->wp base dir.
else
	$pnPathPrefix = $pnPathBase.'../../../'; // cgplugins->plugins->wpcontent->wp base dir.
		
//if (!$AmazonQueryMgr)
//	@include_once("cga-config.php");

require_once($pnPathBase.'helper_fns.php');

function get_page_titles($before='', $after='')
{
	global $firstpagetitle, $numpagetitles, $pagetitles;
	$output = '';
	if (!empty($firstpagetitle))
		$output .= $before.$firstpagetitle.$after;
	$i = 1;
	foreach ($pagetitles as $pagename)
	{
		if (empty($pagename)) $pagename = "Page $i";
		$output .= $before.$pagename.$after;
	}
	die($output);
	return $output;
}

function the_page_titles($before='', $after='')
{
	$output = get_page_titles($before, $after);
	echo $output;
}

function post_pagename($posts)
{
	global $force_single_page;
	global $numpagetitles, $pagetitles;
	global $multipage;

	if (count($posts)!=1) return($posts); // unchanged.

	$regexpPageAll = '/<!--nextpage(.*)?-->/';
	if (preg_match($regexpPageAll, $posts[0]->post_content)) // some kind of nextpage thing...
	{
		if ($force_single_page)
			$posts[0]->post_content = preg_replace($regexpPageAll, '', $posts[0]->post_content);
		else
		{
			$multipage = 1; // !!!!!TBD do I need to be setting this myself???
			// new custom-page-title pullout.
			$regexpPageTitle = '/<!--nextpage:(.+)?-->/';
			$numpagetitles = preg_match_all($regexpPageTitle, $posts[0]->post_content, $sometitles, PREG_PATTERN_ORDER);
			$pagetitles = $sometitles[1]; // grab the array of matches.
			$posts[0]->post_content = preg_replace($regexpPageTitle, "<!--nextpage--><h4 class='pagetitle'>\${1}</h4>", $posts[0]->post_content);
		}
	}
		
	return($posts); // we modify the internals only.
}


function link_page_names($before='<br />', $after='<br />',
					$linktype='number', $nextpagelink='next page', $previouspagelink='previous page',
					$befpage=' ', $aftpage='', $pagelink='%', $befcurr='', $aftcurr='', $more_file='', $max_links=0) {
	global $id, $page, $numpages, $multipage, $more;
	global $pagenow;
	global $firstpagetitle, $numpagetitles, $pagetitles;
	
	if ($more_file != '') {
		$file = $more_file;
	} else {
		$file = $pagenow;
	}
	
	if (($multipage))
	{ // && ($more)) {	
		$before = str_replace('%', $numpages, $before);
		echo $before;
		
		if (/*$more &&*/ $linktype=='next' || $linktype=='both') // do prev page link
		{
			$i=$page-1;
			if ($i)// /*&& $more*/)
			{
				echo $befpage;
				if ('' == get_settings('permalink_structure')) {
					echo '<a href="'.get_permalink().'&amp;page='.$i.'">';
				} else {
					echo '<a href="'.get_permalink().$i.'/">';
				}
				echo $previouspagelink;
				echo '</a>&nbsp;&nbsp;';
				echo $aftpage;
			}
		}

		if ($linktype=='number' || $linktype=='both' || $linktype=='title')
		{
			$k = 0;
			$sp = 1;
			if ($max_links && $page>1)
			{
				$sp = $page-1;
				echo "... ";
			}
			for ($i = $sp; $i < ($numpages+1) && (!$max_links || $k < 3); $i = $i + 1)
			{
				$k++;
				echo $befpage;

				if ($linktype == 'title') // new case!
				{
					if ($i==1)
						$pagename = $firstpagetitle;
					else
						$pagename = $pagetitles[($i-2)];
					if (empty($pagename)) $pagename = "Page $i";
				}
				else // normal page-numbering case
				{
					$pagename = $i;
				}
				
				if (($i != $page) || ((!$more) && ($page==1)))
				{
					if ('' == get_settings('permalink_structure'))
					{
						echo '<a href="'.get_permalink().'&amp;page='.$i.'"';
					} else {
						echo '<a href="'.get_permalink().$i.'/"';
					}
					if ($linktype=='title')
						echo ' title="'.$pagename.'"';
					echo '>';
				}
				
				$j=str_replace('%',"$pagename",$pagelink);
				if ($i==$page)
					$j=$befcurr.$j.$aftcurr;
				echo $j;
				if (($i != $page) || ((!$more) && ($page==1)))
					echo '</a>';
				echo $aftpage;
			}
			if ($i < ($numpages+1)) // ran out early, bc of max?
				echo " ...";
		}

		if (/*$more &&*/ $linktype=='next' || $linktype=='both') // do next page link
		{
			$i=$page+1;
			if ($i<=$numpages) // && $more)
			{
				if ($linktype == 'both') echo '&nbsp;&nbsp;';
				
				echo $befpage;
				if ('' == get_settings('permalink_structure')) {
					echo '<a href="'.get_permalink().'&amp;page='.$i.'">';
				} else {
					echo '<a href="'.get_permalink().$i.'/">';
				}
				echo $nextpagelink;
				echo '</a>';
				echo $aftpage;
			}
		}

		echo $after;
	}
}

?>