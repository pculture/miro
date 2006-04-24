<?php
require_once("include.php");
require_once("version.php");

get_upgrade_scripts( get_version(), get_datastore_version() );
set_datastore_version( get_version() );

?>
<h3>All Set!</h3>
<a href="admin.php">Back to Broadcast Machine</a>