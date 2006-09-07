<?php

$last_db_error = "";

if (!function_exists('db_getresults'))
{
	function db_getresults($query, $type=null, $from=null)
	{
		global $wpdb;
		if ($type)
			return $wpdb->get_results($query, $type);
		else
			return $wpdb->get_results($query);
	}
}


if (!function_exists('db_getrow'))
{
	function db_getrow($query, $type=null, $rownum=0, $from=null)
	{
		global $wpdb;
		if ($type)
			return $wpdb->get_row($query, $type, $rownum);
		else
			return $wpdb->get_row($query);
	}
}



if (!function_exists('db_runquery'))
{
	function db_runquery($query, $from=null)
	{
		global $wpdb;
		return $wpdb->query($query);
	}
}


if (!function_exists('db_lasterror'))
{
	function db_lasterror()
	{
		if (mysql_error())
			return(true);
//		global $wpdb;
//		return $wpdb->query($query);
	}
}



?>