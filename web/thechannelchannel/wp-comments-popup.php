<?php
if (!$_SERVER['HTTP_REFERER'] == dirname(__FILE__) . '/wp-comments.php')
{ 
	die ('Error: This file cannot be used on its own.'); 
}
