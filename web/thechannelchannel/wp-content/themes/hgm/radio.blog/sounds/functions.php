<?

function webPath() {
    $webPath = 'http://'.getenv('HTTP_HOST').str_replace(basename(getenv('REQUEST_URI')), '',getenv('REQUEST_URI') );
    return $webPath;
}

function getTracks($path, $ext) {
    $out = array();
    if ($dir = opendir($path)) {
        while (false !== ($file = readdir($dir))) {
            if ( strrchr($file,'.') == $ext) {
    			$last_mod = filemtime($path.'/'.$file);
    			while ( isset($out[$last_mod]) ) {
                    $last_mod++; 
                } 
    			$out[$last_mod] = utf8_encode(str_replace("&","&amp;",$file));
            }
    	}
    }
    
    closedir($dir);
    return $out;
}



?>