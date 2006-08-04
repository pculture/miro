<?php
require_once("include.php");
require_once("version.php");

get_upgrade_scripts( version_number(), get_datastore_version() );
set_datastore_version( version_number() );

?>
<h3>All Set!</h3>
<a href="admin.php">Back to Broadcast Machine</a>