<?php

$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);

if (!isset($user_level) && function_exists('get_currentuserinfo'))
	get_currentuserinfo(); // cache away in case hasn't been yet...

$tablerelatedposts = $table_prefix.'cg_related';

$relatedPath = dirname(__FILE__).'/';
require_once($relatedPath."db_fns.php");

// should be able to do:
$myRedirect = $_SERVER["REQUEST_URI"];

$floatRelatedButtons = true; // if false, does them inline...

function cg_setcookie($name, $val='')
{
	$setval = $val=='' ? FALSE : $val;
	$rawtime = time();
	$settime = $val=='' ? ($rawtime-3600) : ($rawtime+360000); // 100 hours..
	setcookie($name, $setval, $settime, '/');
}

//========================================
function get_related_posts($post_id, $none='', $showTypes=false)
{
	global $tableposts, $tablerelatedposts;
	global $siteurl, $blogfilename, $querystring_start, $querystring_equal;
	
	$output = '';

	$rquery =  "SELECT * FROM $tableposts AS t1
							LEFT JOIN $tablerelatedposts AS t2
							ON t2.post_id = $post_id
							WHERE (t1.post_status='publish' || t1.post_status='sticky')
							AND (t2.related_id = t1.ID)";
	if ($showTypes) // only for CHAITGEAR right now...
		$rquery .= " ORDER BY t1.post_type ASC, t1.post_date DESC";
	$results = db_getresults($rquery, OBJECT, "get_related_posts");

	$c = count($results); 	
	if ($c<=0) return $none?"<ul><li><i>$none</i></li></ul>":null;

	$output .= '<ul>';
	$i = 0;
	$lastType = 0;
	foreach ($results as $result)
	{
		$postID = $result->ID;
		$post_title = stripslashes($result->post_title);
		if (isset($result->post_type)) // on CHAITGEAR, unset elsewhere...
		{
			$type = $result->post_type;
			if ($lastType != $type)
			{
				$lastType = $type;
				$currType = get_the_type_by_ID($type);
				if (!empty($currType))
				{
					$typeName = stripslashes($currType->cat_name);
					$output .= "<li class='submenugroup'>$typeName</li>";
					$i = 0;
				}
			}
		}
		$output .= '<li><a href="'.$siteurl.'/'.$blogfilename.$querystring_start.'p'.$querystring_equal.$postID .'"';
		$output .= ' title="'.$post_title.'"';
		$output .= '>'.$post_title.'</a></li>';
	}
	$output .= '</ul>';
	
	return($output);
}

//========================================
function check_related_setup()
{
	global $user_level;

	if ($user_level < 4) return; // only primary admins!

	$vrBegin = $_POST["vr_begin"];
	$vrRelate = $_POST["vr_relate"];
	$vrDone = $_POST["vr_done"];

//echo "begin = $vrBegin, relate = $vrRelate, done = $vrDone<br/>... ".$_COOKIE['wprelated'];
		
	if (!$vrDone && !$vrBegin && !$vrRelate) return;
	
	if ($vrRelate)
	{
		$relPost = get_current_related();
		$postID = abs($vrRelate);
		if ($relPost == $postID) return; // we're done, no self-relation!
		$areRelated = get_post_related($relPost, $postID);
		if (!$areRelated) // relate it
		{
			if ($vrRelate>0)
				add_related_post($relPost, $postID);
		}
		else
		{
			if ($vrRelate<0)
				remove_related_post($relPost, $postID);
		}
	}
	else
	if ($vrBegin)
	{
		begin_add_related($vrBegin);
	}
	else //$vrDone
	{
		//die("done");
		done_add_related();
	}
	
	unset($_POST["vr_begin"]);
	unset($_POST["vr_relate"]);
	unset($_POST["vr_done"]);
	
	check_related_setup(); // recurse -- will only happen once, since we unset the vars.
}

//========================================
// this MUST be being called within the
// posts loop, so that $post is valid...
function setup_related_quickbuttons($doecho = true)
{
	global $post, $user_level, $myRedirect;
	global $RELATED_STYLES;
	
	if ($user_level < 4) return; // only primary admins!

	$output = '';
		
	if ($relPost = get_current_related()) // then related matching active
	{		
		$postID = $post->ID;
		$redirect = htmlspecialchars($myRedirect);
		if ($post && $postID && $postID != $relPost) //then show buttons
		{
			$areRelated = get_post_related($relPost, $postID);
			if (!$areRelated) $relateName = "+";
			else $relateName = "-";
			$output .= '<form name="vr_relate_input" action="'.$redirect.'" method="post" class="vr_inputinline">';
			$output .= '<input type="hidden" name="vr_relate" value="'.($areRelated?(0-$postID):$postID).'" />';
			$output .= '<input type="submit" name="submit" value="'.$relateName.'" class="vr_button" />';
			$output .= '</form>';
		}
	}
	
	if ($doecho)
		echo($output);
	else
		return($output);
}

	
function setup_related_buttons($doecho=true, $perPost=false, $sBegin='', $sDone='', $noForms=false)
{
	global $user_level, $wp_query, $posts, $post, $p, $myRedirect;

	if ($user_level < 4) return; // only primary admins!
	
	$relPost = get_current_related();

	// since WP doesn't always keep $p around any more, we fake it.
//	if (!isset($p) || empty($p))
	{
		$p = null;
		if (isset($post))
			$p = $post->ID;
		else
		if (1 == count($posts))
			$p = $posts[0]->ID;
	}

	if ($perPost && $relPost && $relPost!=$p) return; // then we can early exit if multiple posts...

	$output = '';
	if ($relPost) // then related matching active
	{
		$redirect = htmlspecialchars($myRedirect);
		if ($p && $p != $relPost) //then show buttons
		{
			$areRelated = get_post_related($relPost, $p);
			if (!$areRelated) $relateName = "Relate This";
			else $relateName = "Unrelate This";
			$output .= '<form name="vr_relate_input" action="'.$redirect.'" method="post" class="vr_inputinline"><input type="hidden" name="vr_relate" value="'.($areRelated?(0-$p):$p).'" /><input type="submit" name="submit" value="'.$relateName.'" class="vr_button" /></form>';
		}				
		
		$output .= '<form name="vr_done_input" action="'.$redirect.'" method="post" class="vr_inputinline"><input type="hidden" name="vr_done" value="1" /><input type="submit" name="submit" value="'.($sDone?$sDone:"Done Relating").'" class="vr_button" /></form>';
	}
	else
	if ($p)
	{ // not yet active
		$output .= '<form name="vr_begin_input" action="'.$redirect.'" method="post" class="vr_inputinline"><input type="hidden" name="vr_begin" value="'.$p.'" /><input type="submit" name="submit" value="'.($sBegin?$sBegin:"Begin Relating").'" class="vr_button" /></form>';
	}
	
	if ($doecho)
		echo $output;
	else
		return($output);
}


//========================================
function begin_add_related($post_id)
{
	global $myRedirect;
	if (empty($post_id)) return;
	cg_setcookie('wprelated', $post_id);
	$redirect = htmlspecialchars($myRedirect);
	header("Location: $redirect");
}

//========================================
function done_add_related()
{
	global $myRedirect;
//	$post_id = get_current_related();
	cg_setcookie('wprelated');
	$redirect = htmlspecialchars($myRedirect);
	header("Location: $redirect");
}

//========================================
function get_current_related()
{
	if (!isset($_COOKIE['wprelated']))
		return null;
//	die(gettingrelated);	
	$relPost = $_COOKIE['wprelated'];
//	die("wprelated = $relPost");
	return $relPost;
}

//========================================
function get_post_related($post_id, $related_id)
{
	global $tablerelatedposts;
	// first, make sure it isn't there.	
	$rquery = "SELECT rel_id FROM $tablerelatedposts WHERE post_id = $post_id AND related_id = $related_id";
	$results = db_getresults($rquery, OBJECT, "add_related_posts");
	if (empty($results))
	{
		return false;
	}
	
//	die ("already related $post_id, $related_id");
	return true;
}


//========================================
function add_related_post($post_id, $related_id)
{
	global $tablerelatedposts;
	
	// sanity check!
	if ($post_id == $related_id) return;

//	die("add $post_id, $related_id");
	if (get_post_related($post_id, $related_id)) return;
		
	// ADD IT.
	$rquery = "INSERT INTO $tablerelatedposts (post_id, related_id) VALUES ('$post_id', '$related_id')";
	$results = db_runquery($rquery, OBJECT, "add_related_posts");
}

//========================================
function remove_related_post($post_id, $related_id)
{
	global $tablerelatedposts;
	db_runquery("DELETE FROM $tablerelatedposts WHERE post_id = $post_id AND related_id = $related_id", OBJECT, "remove_related_post");
}

//========================================
function install_related_table()
{
	global $tablerelatedposts;
	echo "<p>... trying to create table ...</p>";
	$result = db_runquery("CREATE TABLE `$tablerelatedposts` (
											  `rel_id` int(11) NOT NULL auto_increment,
											  `post_id` int(11) NOT NULL default '0',
											  `related_id` int(11) NOT NULL default '0',
											  PRIMARY KEY  (`rel_id`),
											  KEY `post_id` (`post_id`,`related_id`)
											) TYPE=MyISAM;");
	if (empty($result))
		echo "<p>... installed without error ...</p>";
	else
		echo "<p>... installation returned error $result ...</p>";
}

//========================================
function uninstall_related_table()
{
	global $tablerelatedposts;
	$result = db_runquery("DROP TABLE `$tablerelatedposts`");
}

//========================================
//========================================
function append_relation_buttons( $thing )
{
	$qb = setup_related_buttons(false, true, '>', '!') . setup_related_quickbuttons(false);
	return ($thing . $qb);
}

function action_related_styles()
{
	global $floatRelatedButtons;
	if ($floatRelatedButtons)
		$displaycode = "float:right;";
	else
		$displaycode = "display:inline;";
	?>
	<style type="text/css">
		form.vr_inputinline {
			<?php echo $displaycode; ?>
			background: none;
		}
		form input.vr_quickbutton {
			<?php echo $displaycode; ?>
			background: none;
			font-size: 80%;
			margin-bottom: 1px;
			cursor: pointer;
		}
		form input.vr_button {
			font-size: 80%;
			margin-bottom: 1px;
			cursor: pointer;
		}
	</style>
	<?php
}

//========================================
//========================================

if ( strstr($REQUESTED, 'cg-plugins/cg-related.php') ) // under cg plugins
{
	if (!isset($user_level) && function_exists('get_currentuserinfo'))
		get_currentuserinfo(); // cache away in case hasn't been yet...
	if ($user_level<4) die("You need a higher access level.");
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
	
	$findvars = array('vr_action', 'vr_options');
	
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
	
	if ($vr_action=='create')
	{
//		$showingErrors = $wpdb->show_errors;
//		$wpdb->hide_errors();
		?>
			<div class="wrap">
				<h2>CG-Related</h2>
				<p>CG-Related installing into WP database...</p>
				<?php install_related_table(); ?>
				<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="vr_action" value="none" />
					<input type="submit" name="submit" value="Done" class="search" />
				</form>
			</div>
		<?php
//		if ($showingErrors) $wpdb->show_errors();
	}
	else
	{
		// test database...
		$wpdb->hide_errors();
		$qnumitems = db_getrow("SELECT COUNT(*) as num FROM $tablerelatedposts", OBJECT, 0, "admin - referrer count");
		$wpdb->show_errors();
		if (!empty($qnumitems)) 
		{
			$qnumitems = $qnumitems->num; // just grab the count.
			?>
				<div class="wrap">
					<h2>CG-Related:</h2>
					<p>Installed, <?php echo $qnumitems; ?> relations established.</p>
				</div>
			<?php
		}
		else // likely means table not exist, test error...
		if (db_lasterror()) // was error, table doesn't exist??
		{
		?>
			<div class="wrap">
				<h2>CG-Related</h2>
				<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
					<p>Cannot locate any existing CG-Related data.</p>
					<input type="hidden" name="vr_action" value="create" />
					<input type="submit" name="submit" value="Create CG-Related Table" class="search" />
				</form>
			</div>
		<?php	
		}
	}
}
else
{	
	function related_init()
	{
		global $user_level;

		if (!isset($user_level) && function_exists('get_currentuserinfo'))
			get_currentuserinfo(); // cache away in case hasn't been yet...
		
		// this starts everything off!
		check_related_setup();
	
		// this was a failed attempt to auto-setup the buttons...
		//add_filter( 'the_title', 'related_title_linkage' );
		if (!isset($disableAutoRelatedButtons) || !$disableAutoRelatedButtons)
		{
			if (function_exists('append_relation_buttons'))
				add_filter( 'the_content', 'append_relation_buttons' );
			if (function_exists('action_related_styles'))
				add_action('wp_head', 'action_related_styles');
			//add_filter( 'get_the_time', 'prepend_relation_button' );
		}
	}	
	
	if (function_exists('related_init'))
		add_action('plugins_loaded', 'related_init');
}

?>