<?php
include_once("include.php");

//include saxy parser
require_once('xml_saxy_parser.php');

function startElementHandler($parser, $elementName, $attrArray) {
  global $current_element;
  $current_element = $elementName;
} //startElementHandler

function endElementHandler($parser, $elementName) {

}

function characterHandler($parser, $text) {
  global $current_element;
  global $ds_version;

  if ( $current_element == "version" ) {
    $ds_version = $text;
  }
} //characterHandler

function get_datastore_version() {
  global $data_dir;

  if ( ! file_exists( "$data_dir/version.xml") ) {
    return version_number();
  }
  $xml = file_get_contents("$data_dir/version.xml");

  $saxparser =& new SAXY_Parser();

  //register events
  $saxparser->xml_set_element_handler("startElementHandler", "endElementHandler");
  $saxparser->xml_set_character_data_handler("characterHandler");

  $success = $saxparser->parse($xml);
  global $ds_version;
  if ( $success == false || !isset($ds_version) ) {
    return 20;
  }
  
  return $ds_version;
}

function set_datastore_version($v) {

  //debug_message("set datastore version to $v");

  global $data_dir;

  $xml = '<?xml version="1.0" ?>
<datastore>
  <version>' . $v . '</version>
</datastore>';
  
  $f = fopen("$data_dir/version.xml", 'wb');
  
  flock( $f, LOCK_EX );
  ftruncate($f, 0);
  fwrite($f, $xml);

 // //debug_message($xml);
  
  // make sure the file is flushed out to the filesystem
  fflush($f);
  
  flock( $f, LOCK_UN );
  fclose($f);

  clearstatcache();
}



function upgradeStartElementHandler($parser, $elementName, $attrArray) {
  global $in_script;
  if ( $elementName == "script" ) {
    $in_script = true;
  }
  else if ( $in_script == true ) {
    global $scripts;
    global $current_element;
    $current_element = $elementName;    
  }
} //startElementHandler

function upgradeEndElementHandler($parser, $elementName) {
  global $in_script;
  if ( $elementName == "script" ) {
    $in_script = false;
  }
}

function upgradeCharacterHandler($parser, $text) {
  global $current_element;
  global $scripts;
  global $in_script;

  if ( $in_script == true ) {
    global $current_element;
    global $current_name;

    if ( $current_element == "name" ) {
      $current_name = $text;
    }
    else {
      $scripts[$current_name][$current_element] = $text;
    }
  }

} //characterHandler



function get_upgrade_scripts($from, $to) {

  if ( ! isset($from) ) {
    $from = get_datastore_version();	
  }
  
  if ( ! isset($to) ) {
    $to = get_version();		
  }

  if ( file_exists("upgrades.xml") ) {
  
    $xml = file_get_contents("upgrades.xml");
    $saxparser =& new SAXY_Parser();
  
    //register events
    $saxparser->xml_set_element_handler("upgradeStartElementHandler", "upgradeEndElementHandler");
    $saxparser->xml_set_character_data_handler("upgradeCharacterHandler");

    $success = $saxparser->parse($xml);
    global $scripts;
    $data = $scripts;

    global $store;
  
    foreach( $data as $a ) {
      if ( $store->type() == "MySQL" && $a["type"] == "mysql" && $a["version"] > get_datastore_version() ) {
        if ( !isset($store->prefix) ) {
	  $store->prefix = "";
        }
        $sql = str_replace("__", $store->prefix, $a["action"]);
        debug_message("Action: $sql");
        mysql_query ($sql);
      }	
    }
  }

}
?>
