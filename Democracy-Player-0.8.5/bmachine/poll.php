<?php
/**
 * polling page which gets called from the publish page when the user is
 * uploading a torrent
 *
 * @package BroadcastMachine
 */

$hash = $_GET["i"];

include_once "include.php";

global $data_dir;

if ( preg_match("/^[a-z0-9]+$/", $hash) && file_exists( $data_dir . '/' . $hash ) ) {
	$handle = fopen($data_dir . '/' . $hash, "rb+");
	$torrent = fread($handle, 1024);
	fclose($handle);

?>

<script language="Javascript">
	parent.torrent_name = "<?php echo substr($torrent,0,strlen($torrent) - 8); ?>";
</script>

<?php
} 
else if ( file_exists( $data_dir . '/' . $hash . '.error' ) ) {

	$handle = fopen($data_dir . '/' . $hash . '.error', "rb+");
	$errorstr = fread($handle, 1024);
	fclose($handle);
	
	unlink_file($data_dir . '/' . $hash . '.error');

?>
<script language="Javascript">
	parent.upload_error = "<?php echo $errorstr; ?>";
</script>
<?php
}
?>