<?php
/**
 * Creative Commons license picker
 * @package BroadcastMachine
 */

	$license_url = $_GET["license_url"];
	$license_name = $_GET["license_name"];
?>


<script lanaguage="Javascript">
	frm = window.opener.document.getElementById('post');
	frm.LicenseURL.value = '<?php echo $license_url; ?>';
	frm.LicenseName.value = '<?php echo $license_name; ?>';
	self.close();
</script>