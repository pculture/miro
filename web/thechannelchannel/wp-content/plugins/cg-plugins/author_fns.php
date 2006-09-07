<?php

function link_authors_by_ID($sep = ' :: ', $pre='', $post='')
{
	global $tableusers, $wpdb;

	$file = "$siteurl/$blogfilename";

	$query = ("SELECT * from $tableusers ORDER BY user_nicename");
	$results = $wpdb->get_results($query);

	$i = 0;
	foreach($results as $user)
	{
		if ($i > 0) echo $sep;
		$i++;
		echo $pre;
		echo "<a href='$file?author=$user->ID'>";
		echo "$user->user_nickname";
		echo "</a>";
		echo $post;
		echo "\n";
	}
}

?>