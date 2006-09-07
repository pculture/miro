<?php

$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);

$poPath = dirname(__FILE__).'/';

if (!isset($po_posttitle_prefix))
	$po_posttitle_prefix = ''; // could be 'Sticky: ', 'HOT! ', etc.  SET IN YOUR WP-CONFIG.

require_once($poPath."db_fns.php");

$po_table = $table_prefix."cg_postorder";
$po_disabled = false;

// should be able to do:
$myRedirect = $_SERVER["REQUEST_URI"];

$floatOrderButtons = true; // if false, does them inline...


//======================================
function postorder_add_join($join)
{
	global $wpdb,$po_table;
	global $po_disabled;
	$po_disabled = (
			is_plugin_page()								// we don't process on the plugins page ever
		||	is_single()									// no need to process on single post requests
		||	is_feed()										// feeds should be date ordered, never postorder
		//||	 $pagenow == 'post.php'						// for the moment, we DO want to postorder posts in admin screens!
		//||	 $pagenow == 'edit.php' 					// for the moment, we DO want to postorder posts in admin screens!
					); // done.
					
	if (!$po_disabled)
		$join .= " LEFT JOIN {$po_table} ON ({$po_table}.po_post_ID = $wpdb->posts.ID)"; 

	return $join;
}

//======================================
function postorder_add_orderby($order)
{
	global $po_table;
	global $po_disabled;
	
	if (!$po_disabled)
		$order = "{$po_table}.postorder DESC,".$order;	
	
	return $order;
}

//======================================
function postorder_tag_title($title)
{
	global $post, $po_posttitle_prefix;
	if (isset($post->postorder))
		$title = $po_posttitle_prefix.$title;	
	return $title;
}

//========================================
function cache_post_order($force=false)
{
	global $po_table, $po_cache;
	
	if (!$force && isset($po_cache)) return;
	
	$qres = db_getresults("SELECT * FROM $po_table", OBJECT, 0, "admin - po cache");
	foreach ($qres as $apost)
		$po_cache[$apost->po_post_ID] = $apost;
}

//========================================
function get_post_order($post_id)
{
	global $po_table, $po_cache;
	
	cache_post_order();	
	if (isset($po_cache[$post_id]))
		return $po_cache[$post_id]->postorder;
		
	return FALSE;
}

//========================================
function add_post_order($post_id)
{
	global $po_table;
	
	// sanity check!
	if (get_post_order($post_id)!==FALSE) return;
		
	//die("add $post_id");
	// ADD IT.
	$rquery = "INSERT INTO $po_table (po_post_ID, postorder) VALUES ('$post_id', '1')";
	$results = db_runquery($rquery, OBJECT, "add_post_order");
}

//========================================
function remove_post_order($post_id)
{
	global $po_table;
	//die("remove $post_id");
	db_runquery("DELETE FROM $po_table WHERE po_post_ID = '$post_id'", OBJECT, "remove_post_order");
}

//========================================
function post_order_up($post_id)
{
	global $po_table;
	
	// sanity check!
	$order = get_post_order($post_id);
	if ($order===FALSE) return;
	if ($order>=999) return; // cap how high post order can be.
		
	$rquery = "UPDATE $po_table SET postorder=postorder+1 WHERE po_post_ID=$post_id";
	$results = db_runquery($rquery, OBJECT, "post_order_up");
}


//========================================
function post_order_down($post_id)
{
	global $po_table;
	
	// sanity check!
	$order = get_post_order($post_id);
	if ($order===FALSE) return;
	if ($order<=1) return; // lower bound at 1, as non-ordered posts are null (zero)
		
	$rquery = "UPDATE $po_table SET postorder=postorder-1 WHERE po_post_ID=$post_id";
	$results = db_runquery($rquery, OBJECT, "post_order_down");
}


//========================================
function setup_po_quickbuttons($doecho=true, $noForms=false)
{
	global $user_level, $wp_query, $posts, $post, $p, $myRedirect;

	if ($user_level < 4) return; // only primary admins!
	
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

	$output = '';
	if ($p)
	{
		//$redirect = htmlspecialchars($myRedirect);
		if (get_post_order($p))
		{
			$output .= '<form name="po_remove_input" action="'.$redirect.'" method="post" class="po_inputinline"><input type="hidden" name="po_remove" value="'.$p.'" /><input type="submit" name="submit" value="X" class="po_button" title="Un-Order This Post" /></form>';
		}
		else
		{ // not yet active
			$output .= '<form name="po_add_input" action="'.$redirect.'" method="post" class="po_inputinline"><input type="hidden" name="po_add" value="'.$p.'" /><input type="submit" name="submit" value="O" class="po_button" title="Order This Post" /></form>';
		}
	}
		
	if ($doecho)
		echo $output;
	else
		return($output);
}

//========================================
function install_po_table()
{
	global $po_table;
	echo "<p>... trying to create table ...</p>";
	$result = db_runquery("CREATE TABLE `$po_table` (
											  `po_id` int(11) NOT NULL auto_increment,
											  `po_post_ID` bigint(20) NOT NULL default '0',
											  `postorder` tinyint(6) NOT NULL default '0',
											  PRIMARY KEY  (`po_id`),
											  KEY `post_id` (`po_post_ID`,`postorder`)
											) TYPE=MyISAM;");
	if (empty($result))
		echo "<p>... installed without error ...</p>";
	else
		echo "<p>... installation returned error $result ...</p>";
}

//========================================
function uninstall_po_table()
{
	global $po_table;
	$result = db_runquery("DROP TABLE `$po_table`");
}

//========================================
function append_po_buttons( $thing )
{
	$qb = setup_po_quickbuttons(false);
	return ($thing . $qb);
}

//========================================
function action_po_styles()
{
	global $floatOrderButtons;
	if ($floatOrderButtons)
		$displaycode = "float:right;";
	else
		$displaycode = "display:inline;";
	?>
	<style type="text/css">
		form.po_inputinline {
			<?php echo $displaycode; ?>
			background: none;
		}
		form input.po_quickbutton {
			<?php echo $displaycode; ?>
			background: none;
			font-size: 80%;
			margin-bottom: 1px;
			cursor: pointer;
		}
		form input.po_button {
			font-size: 80%;
			margin-bottom: 1px;
			cursor: pointer;
		}
	</style>
	<?php
}

//========================================
//========================================
function check_postorder_handler()
{
	global $user_level, $po_cache;
	
	if ($user_level < 4) return; // only primary admins!

	$po_add = $_POST["po_add"];
	$po_remove = $_POST["po_remove"];
	$po_up = $_POST["po_up"];
	$po_down = $_POST["po_down"];
	unset($_POST["po_add"]);
	unset($_POST["po_remove"]);
	unset($_POST["po_up"]);
	unset($_POST["po_down"]);

	if (!$po_add && !$po_remove && !$po_up && !$po_down) return;

	if ($po_add || $po_remove)
	{
		if ($po_remove)
			remove_post_order($po_remove);
		else
			add_post_order($po_add);
	}
	
	unset($po_cache);
	cache_post_order(true);
}


//========================================

if ( strstr($REQUESTED, 'cg-plugins/cg-postorder.php') ) // under cg plugins
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
	
	$findvars = array('po_action', 'po_add', 'po_remove', 'po_post');
	
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
		// SANITY CHECK INCOMING DATA!
		if ($$avar) // check for bad content
			if (FALSE!==strpos($$avar, 'http:')) // NO URIs AT ALL IN THESE COMMANDS!
				$$avar = '';
	}
	
	if ($po_action=='create')
	{
//		$showingErrors = $wpdb->show_errors;
//		$wpdb->hide_errors();
		?>
			<div class="wrap">
				<h2>CG-PostOrder</h2>
				<p>CG-PostOrder installing into WP database...</p>
				<?php install_po_table(); ?>
				<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="po_action" value="none" />
					<input type="submit" name="submit" value="Done" class="search" />
				</form>
			</div>
		<?php
//		if ($showingErrors) $wpdb->show_errors();
	}
	else
	if ($po_add || $po_remove)
	{
		if ($po_remove)
			remove_post_order($po_remove);
		else
			add_post_order($po_add);

		$p = $po_add?$po_add:$po_remove;
		
		$po_status = "Post $p: ".($po_add?'ADDED':'REMOVED').".";
	}
	else
	if (($po_action=='up' || $po_action=='down') && $po_post)
	{
		if ($po_action=='up')
			post_order_up($po_post);
		else
			post_order_down($po_post);

		$po_status = "Post $po_post re-ordered.";
	}
	
	if ($po_action!='create')
	{
		// test database...
		$wpdb->hide_errors();
		$qnumitems = db_getrow("SELECT COUNT(*) as num FROM $po_table", OBJECT, 0, "admin - postorder count");
		$wpdb->show_errors();
		if (!empty($qnumitems)) 
		{
			$qnumitems = $qnumitems->num; // just grab the count.
			$qposts = db_getresults("SELECT ID, post_title, post_date, postorder FROM $tableposts, $po_table WHERE (po_post_ID = ID) ORDER BY postorder DESC, post_date DESC", OBJECT, 0, "admin - postorder count");
			?>
				<style>
					tr.rodd { background: #fefefe; }
					tr.reven { background: #eeefee; }
					tr.rcurr { background: #e0ffe0; }
					tr.rhead { background: #aabbdd; }
					th.inbtn, td.inbtn { background: white; }
					div#postatus {
								font-weight: bold;
								border-top: 1px dashed #444444; border-bottom: 1px solid #444444;
								margin-bottom: 12px;
								padding: 4px;
								}
				</style>
								
				<div class="wrap">
					<h2>CG-PostOrder:</h2>
					<p>Installed, <?php echo count($qposts); ?> posts marked for 'sticky' post-ordering.</p>
					<div id="postatus">&nbsp;&nbsp;<?php echo $po_status; ?></div>
					<?php if (count($qposts)) { ?>
						<table>
							<tr class="rhead"><th width="30" class="inbtn"></th><th width="30" class="inbtn"></th><th width="60">Level</th><th width="600">Post Title</th><th width="60">Post ID</th></tr>
						<?php
							$i = 0;
							foreach($qposts as $apost)
							{
								$i++;
								echo '<tr class="';
								if ($apost->ID==$po_post) echo 'rcurr';
								else echo (($i%2)?'rodd':'reven');
								echo '">';
									if ($apost->postorder>1)
										echo '<td class="inbtn"><form name="po_down" action="'.$myRedirect.'" method="post" class="po_inputinline"><input type="hidden" name="po_action" value="down" /><input type="hidden" name="po_post" value="'.$apost->ID.'" /><input type="submit" name="submit" value="&#8659;" class="po_button" title="Shift This Post Down" /></form></td>';
									else
										echo '<td class="inbtn"></td>';
									echo '<td class="inbtn"><form name="po_up" action="'.$myRedirect.'" method="post" class="po_inputinline"><input type="hidden" name="po_action" value="up" /><input type="hidden" name="po_post" value="'.$apost->ID.'" /><input type="submit" name="submit" value="&#8657;" class="po_button" title="Shift This Post Up" /></form></td>';
									echo "<td align=center>$apost->postorder</td>";
									echo "<td>$apost->post_title</td>";
									echo "<td align=center>$apost->ID</td>";
								echo "</tr>";
							}
						?>
						</table>
					<?php } ?>
				</div>
			<?php
		}
		else // likely means table not exist, test error...
		if (db_lasterror()) // was error, table doesn't exist??
		{
		?>
			<div class="wrap">
				<h2>CG-PostOrder</h2>
				<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
					<p>Cannot locate any existing CG-PostOrder data.</p>
					<input type="hidden" name="po_action" value="create" />
					<input type="submit" name="submit" value="Create CG-PostOrder Table" class="search" />
				</form>
			</div>
		<?php	
		}
	}
}
else
{
	function postorder_init()
	{
		global $user_level;

		if (!isset($user_level) && function_exists('get_currentuserinfo'))
			get_currentuserinfo(); // cache away in case hasn't been yet...
		
		//======================================
		// for the moment, DON'T apply ordering to admin queries...
		if (function_exists('postorder_add_join'))
			add_filter('posts_join', 'postorder_add_join');
		if (function_exists('postorder_add_orderby'))
			add_filter('posts_orderby', 'postorder_add_orderby');
		if (function_exists('postorder_tag_title'))
			add_filter('the_title', 'postorder_tag_title');
		
		if ($user_level>4)
		{
			check_postorder_handler();
			
			if (!isset($disableAutoOrderButtons) || !$disableAutoOrderButtons)
			{
				if (function_exists('append_po_buttons'))
					add_filter('the_content', 'append_po_buttons' );
				if (function_exists('action_po_styles'))
					add_action('wp_head', 'action_po_styles');
				//add_filter( 'get_the_time', 'prepend_relation_button' );
			}
		}
	}
	
	if (function_exists('postorder_init'))
		add_action('plugins_loaded', 'postorder_init');
}

?>