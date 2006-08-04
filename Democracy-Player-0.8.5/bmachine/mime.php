<?php
include_once "include.php";

/**
 * try and figure out the content-type of the specified URL
 * @returns content-type, and sets $errstr if something goes wrong
 */
function get_content_type( $file_url, &$errstr ) {

  if ( is_local_file($file_url) ) {
    $fname = local_filename($file_url);
    return mime_content_type("torrents/" . $fname);
  }
  else {
    $headers = @bm_get_headers($file_url, 1);
    
    if ( ! $headers || stristr($headers[0], "404") != 0 ) {

      $errstr = "404";
			
      // if this is a URL that is reporting a 404, let's guess the mime type so 
      // that if the user saves the file anyway, we have a chance of reporting the mime
      // type in RSS, etc.
      return get_mime_from_extension($file_url);
    }
		
    return $headers["content-type"];
  }
}


/**
 * given a filename, try and figure out the mimetype from its extension
 * @returns mimetype, or false if we didn't find a valid type
 */
function get_mime_from_extension($filename) {

  $mimes = array(
		 '.mid' => 'audio/midi',
		 '.midi' => 'audio/midi',
		 '.mpga' => 'audio/mpeg',
		 '.mp2' => 'audio/mpeg',
		 '.mp3' => 'audio/mpeg',
		 '.m3u' => 'audio/x-mpegurl',
		 '.ram' => 'audio/x-pn-realaudio',
		 '.rm' => 'audio/x-pn-realaudio',
		 '.rpm' => 'audio/x-pn-realaudio-plugin',
		 '.ra' => 'audio/x-realaudio',
		 '.wav' => 'audio/x-wav',
		 '.mpeg' => 'video/mpeg',
		 '.mpg' => 'video/mpeg',
		 '.mpe' => 'video/mpeg',
		 '.qt' => 'video/quicktime',
		 '.mov' => 'video/quicktime',
		 '.mxu' => 'video/vnd.mpegurl',
		 '.avi' => 'video/x-msvideo',
		 '.m4p' => 'video/mp4v-es',
		 '.mp4' => 'video/mp4v-es',
		 '.wma' => 'audio/x-ms-wma',
		 '.asf' => 'video/x-ms-asf',
		 '.flv' => 'video/x-flv',
		 '.m2v' => 'video/mpeg2-video'
		 );

  $ext = substr($filename, strrpos($filename, '.')); // get the extension with a dot
  
  if ( isset($mimes[strrchr($filename, '.')]) ) {
    $mime = $mimes[strrchr($filename, '.')];
    
    if ( isset($mime) && $mime != "" ) {
      return $mime;
    }
  }
  
  return false;
  
}
?>