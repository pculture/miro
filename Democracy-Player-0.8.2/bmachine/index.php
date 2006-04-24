<?php
/**
 * Broadcast Machine index page
 * @package Broadcast Machine
 */

require_once("include.php");

global $settings;

if ($settings["DefaultChannel"] != "") {
  header('Location: ' . channel_link($settings["DefaultChannel"]) );
  exit;
}

update_base_url();

render_index_page();

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>