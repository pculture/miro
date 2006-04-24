<?php
if (! defined('SIMPLE_TEST')) {
	define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class SetupTest extends BMTestCase {

  function IncludeTest() {
    $this->BMTestCase();
  }
  
  /**
   * test version_number function
   */
  function testGetVersionNumber() {
    $v = version_number();
    $this->assertTrue($v);
  }
  
  /**
   * test our get_version function
   */
  function testGetVersionString() {
    $v = get_version();
    $this->assertTrue($v != "");
  }
  
  /**
   * test get_base_url
   */
  function testGetBaseURL() {
    $url = get_base_url();
    $this->assertTrue($url != "");
  }
  
  /**
   * test bencode and bdecode functions
   */
  function test_bencode() {
    $data = array();
    $e1 = array(
		"val1" => 1,
		"val2" => "value"
		);
    $e2 = array(
		"val1" => 2,
		"val2" => "other"
		);
    
    $data["element1"] = $e1;
    $data["element2"] = $e2;
    
    $result = bencode($data);
    $this->assertTrue($result != "");
    
    $decoded = bdecode($result);
    
    $out1 = $decoded["element1"];
    $out2 = $decoded["element2"];
    
    $this->assertTrue($out1["val1"] == 1 && $out1["val2"] == "value");
    $this->assertTrue($out2["val1"] == 2 && $out2["val2"] == "other");
  }
  
  function test_site_title() {
    $result = site_title();
    $this->assertTrue(isset($result));
  }
  
  function test_site_description() {
    $result = site_description();
    $this->assertTrue(isset($result));
  }
  
  function TestFirstUser() {
    global $data_dir;
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");	
    
    global $store;
    if ( $store->layer->type() != "MySQL" ) {
      unlink_file($data_dir . "/users");
      unlink_file($data_dir . "/newusers");
    
      $this->assertTrue(!file_exists($data_dir . "/users"), "SetupTest/TestFirstUser: Couldn't remove users file");	
      $this->assertTrue(!file_exists($data_dir . "/newusers"), "SetupTest/TestFirstUser: Couldn't remove newusers file");	
      
      $this->get(	get_base_url() . "admin.php" );
      $newuser_url = get_base_url() . "newuser.php";
      
      $this->assertTrue( $this->getUrl() == $newuser_url, "SetupTest/TestFirstUser: expected new user form but didn't get it");	
      
      $no_email = array();
      $no_email['username'] = "user" . rand(0, 10000);
      $no_email['pass1'] = "password";
      $no_email['pass2'] = "password";
      $no_email['do_login'] = 1;
      
      $this->post( $newuser_url, $no_email );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (no_email)");
      $this->assertWantedPattern("/Please specify an email address/", "SetupTest/TestFirstUser: Expected no email error but didn't get it");
      
      $no_username = array();
      $no_username['email'] = "user" . rand(0, 10000) . "@foo.com";
      $no_username['pass1'] = "password";
      $no_username['pass2'] = "password";
      $no_username['do_login'] = 1;
      
      $this->post( $newuser_url, $no_username );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (no_username)");
      $this->assertWantedPattern("/Please specify a username/", "SetupTest/TestFirstUser: Expected no username error but didn't get it");
      
      $bad_password = array();
      $bad_password['username'] = "user" . rand(0, 10000);
      $bad_password['email'] = "user" . rand(0, 10000) . "@foo.com";
      $bad_password['pass1'] = "password1";
      $bad_password['pass2'] = "password2";
      $bad_password['do_login'] = 1;
      
      $this->post( $newuser_url, $bad_password );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (bad_password)");
      $this->assertWantedPattern("/Your password doesn't match/", "SetupTest/TestFirstUser: Expected bad password error but didn't get it");
    
    
      $no_password1 = array();
      $no_password1['username'] = "user" . rand(0, 10000);
      $no_password1['email'] = "user" . rand(0, 10000) . "@foo.com";
      $no_password1['pass2'] = "password2";
      $no_password1['do_login'] = 1;
      
      $this->post( $newuser_url, $no_password1 );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (no_password1)");
      $this->assertWantedPattern("/Please enter a password/", "SetupTest/TestFirstUser: Expected no password1 error but didn't get it");
    
      $no_password2 = array();
      $no_password2['username'] = "user" . rand(0, 10000);
      $no_password2['email'] = "user" . rand(0, 10000) . "@foo.com";
      $no_password2['pass2'] = "password2";
      $no_password2['do_login'] = 1;
    
      $this->post( $newuser_url, $no_password2 );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (no_password2)");
      $this->assertWantedPattern("/Please enter a password/", "SetupTest/TestFirstUser: Expected no password2 error but didn't get it");

      $gooduser = array();
      $gooduser['username'] = "unittest";
      $gooduser['email'] = "user" . rand(0, 10000) . "@foo.com";
      $gooduser['pass1'] = "unittest";
      $gooduser['pass2'] = "unittest";
      $gooduser['do_login'] = 1;
    
      $this->post( $newuser_url, $gooduser );
      $this->assertResponse("200", "SetupTest/TestFirstUser: didn't get 200 response (gooduser)");
      $this->assertWantedPattern("/was added successfully/", "SetupTest/TestFirstUser: good user add didn't work");
      
      global $store;
      $users = $store->getAllUsers();
    
      $this->assertTrue( count($users) == 1, "SetupTest/TestFirstUser: expected user count of 1 but didn't get it");	
      
      $newusers = $store->layer->getAll("newusers");
      $this->assertTrue( count($newusers) == 0, "SetupTest/TestFirstUser: expected newuser count of 0 but didn't get it");	
    
      $admin_url = get_base_url() . "admin.php";
      $this->get(	$admin_url );
      $this->assertTrue( $this->getUrl() == $admin_url, "SetupTest/TestFirstUser: expected to go to admin page but didn't");	
    }    
  }

}
?>