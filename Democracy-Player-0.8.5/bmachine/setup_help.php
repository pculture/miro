<div class="wrap">
<h2 class="page_name">One Final Step...</h2>
<div class="section">

<p>Before you can use Broadcast Machine, we need to create a few directories.  There are several ways to do this listed below.</p>
<p><em>Once you've completed these steps, reload this page to continue.</em></p>

<div class="section_header">If you want Broadcast Machine to do it for you:</div>
<p>Specify your FTP username and password here, and Broadcast Machine will FTP into your server, 
create the directories and set the permissions for you. You need to know the 'root' address for 
your Broadcast Machine FTP address, which could be something like "public_html/bm/" or "httpdocs/bm".
This information was probably provided to you by your hosting provider.
</p>
<p>This might take a few minutes, please be patient.</p>

<?php
  $permstr = "" . FOLDER_PERM_LEVEL;

$path = guess_path_to_installation();
?>
<form method="POST" action="set_perms.php">
     FTP username: <input type="text" name="username" size="10" /><br />
     FTP password: <input type="password" name="password" size="10" /><br />
     Website Folder: <input type="text" name="ftproot" value="<?php print $path; ?>" size="50" /><br />
     <input type="submit" value="Set Permissions" />
</form>


<p><strong>With a typical FTP program:</strong> 
Create folders in your Broadcast Machine directory named "torrents", "data", "publish", "thumbnails" and "text".  
Then select each folder, view its permissions, and make sure all the checkboxes (readable, writable, 
executable) are checked (should say <?php print $permstr; ?> when correct). Reload this page to continue.</p>


<div class="section_header">If you use command line FTP, or if you have shell access to your server</div>

<p>Log in and type the following:</p>
<pre>cd <?php print $path; ?>

mkdir data
mkdir torrents
mkdir publish
mkdir text
mkdir thumbnails
chmod <?php echo $permstr; ?> data
chmod <?php echo $permstr; ?> torrents
chmod <?php echo $permstr; ?> publish
chmod <?php echo $permstr; ?> text
chmod <?php echo $permstr; ?> thumbnails
</pre>

<p><em>Once you've completed these steps, reload this page to continue.</em></p>

<br />
<p>
<?php
if ( FOLDER_PERM_LEVEL == 0777 || FOLDER_PERM_LEVEL == 777 ) {
?>
Note: giving the directories "777" permissions will allow anyone on the server to full access those directories. If you share a server with others, they may be able to tamper with you Broadcast Machine data files if you use these settings. There may be other settings more appropriate for your server. 
<?php
}
?>
<b>Please, contact your system administrator if you have any questions about permissions.</b>
</p>

</div>
</div>
