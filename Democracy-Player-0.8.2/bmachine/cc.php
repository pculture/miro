<?php
/**
 * Creative Commons license picker
 * @package Broadcast Machine
 */

	$license_url = $_GET["license_url"];
	$license_name = $_GET["license_name"];
?>


<script lanaguage="Javascript">
	frm = window.opener.document.getElementById('post');
	frm.post_license_url.value = '<?php echo $license_url; ?>';
	frm.post_license_name.value = '<?php echo $license_name; ?>';
	self.close();
</script>