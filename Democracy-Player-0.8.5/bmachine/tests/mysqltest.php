<?php
/**
 * @package BMTest
 */


if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

include_once "bmtest.php";

class MySQLTest extends BMTestCase {

	var $prefix = null;

  function MySQLTest($p) {
		$this->prefix = $p;
		$this->BMTestCase();
  }

  /**
   * test the global setup function
   */
  function TestSetup() {
    debug_message("MySQLTest/TestSetup");
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
		global $store;
		$this->assertTrue(isset($store) && $store->type() == 'MySQL', "mysql didnt enable");
  }
	
  /**
   * test getting the type of datastore (we will need to test both mysql/flat at some point
   */
  function TestGetType() {

    debug_message("MySQLTest/TestGetType");
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

    global $store;
    $v = $store->type();
    $this->assertTrue(isset($v) && $v == "MySQL", "DataStoreTest/TestGetType - no type or not mysql");
  }

  /**
   * test the settings load/save functions
   */
  function TestSettings() {

    debug_message("MySQLTest/TestSettings");
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

    global $store;
    global $settings;

    $this->assertTrue( $store->layer->loadSettings() );
    $this->assertTrue( $settings, "DataStoreTest/TestSettings: Didn't load settings");
    $this->assertTrue( $store->saveSettings($settings), "DataStoreTest/TestSettings: Can't Save Settings" );
  }

}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>