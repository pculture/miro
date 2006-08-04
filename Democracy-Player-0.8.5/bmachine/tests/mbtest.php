<?php
/**
 * @package BMTest
 */


if (! defined('SIMPLE_TEST')) {
	define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');
require_once('bmtest.php');

class MBTest extends BMTestCase {

  function MBTest() {
  }

  /**
   * test version_number function
   */
  function TestMBStrToLower() {
    $this->assertTrue("director" == mb_strtolower("Director"), "mb_strtolower isn't working right");
  }

    
  function testLower() {
    // todo - put together a test for this
    //$str = 'IÃTÃRNÃTIÃNÃLIZÃTIÃN';
    //$lower = 'iÃ±tÃ«rnÃ¢tiÃ´nÃ lizÃ¦tiÃ¸n';
    //$this->assertEqual(utf8_strtolower($str),$lower);
  }
    
  function testEmptyString() {
    $str = '';
    $lower = '';
    $this->assertEqual(utf8_strtolower($str),$lower);
  }

} // class MBTest

?>