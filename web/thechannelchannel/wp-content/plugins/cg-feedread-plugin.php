<?php

/*
Plugin Name: CG-Feedread
Plugin URI: http://www.chait.net/index.php?p=238
Description: A simple RSS/RDF feed aggregator.  <em>Works with WordPress</em>, as a hack or Plugin, but also should work on <em>any PHP-based website</em>!  It is smaller and less resource intensive than a lot of other stuff out there, and is flexible enough to allow for quick adoption of new feed formats or fields to output.  Please <a href="http://www.chait.net/index.php?p=48" title="Support CHAITGEAR">find a way to support CHAITGEAR!</a>
Author: David Chait
Author URI: http://www.chait.net
Version: Plugin 1.5.2
*/ 

if ( strstr($_SERVER['REQUEST_URI'], 'plugins.php')  // under admin interface?
||	 is_plugin_page() ) return;

$pluginBasedir = dirname(__FILE__).'/';
		
require_once($pluginBasedir.'cg-plugins/helper_fns.php');

//if (	strstr( $_SERVER['REQUEST_URI'], 'wp-admin' ) ) die(__FILE__."coming in from admin.");

/*
if (isset($_GET['action']) && $_GET['action']=='install-plugin'
&&	(	strstr( $_SERVER['HTTP_REFERER'], '/wp-admin/plugins.php' )
		||strstr( $_SERVER['HTTP_REFERER'], 'feedread.php' ) )
{
	$doingFRInstall = true;
	require_once($pluginBasedir.'../../wp-config.php');
}
*/

include_once($pluginBasedir.'cg-plugins/cg-feedread.php');

/*
if ($doingFRInstall)
{
	feedreadInstall();
	myErrorOutput();
}
*/
?>