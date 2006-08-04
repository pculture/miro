<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class MIMETest extends BMTestCase {

  function MIMETest() {
    $this->BMTestCase();
  }

  function TestMP3File() {
    
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    $file = array();
    $file['Title'] = "unit test " . rand(0, 10000) . ": MP3 Upload";
    $file['Description'] = "description";
    $file['post_do_save'] = 1;
    $file['post_use_upload'] = 1;

    $this->Login();		
    $publish_url = get_base_url() . "publish.php";
    $upload = array();
    $u1 = array();
    $u1["key"] = "post_file_upload";
    $u1["content"] = file_get_contents("tests/testfile.mp3");
    $u1["filename"] = "testfile.mp3";
    $u1["mimetype"] = "audio/mpeg";
    $upload[] = $u1;
    
    $this->post( $publish_url, $file, $upload );
    $code = $this->getResponseCode();
    $this->assertResponse("200", "MIMETest/TestMP3File: got $code instead of expected 200 response");
     // print $this->getContent();
    
    global $store;
    $files = $store->getAllFiles();
    $got_it = $this->Find($files, "Title", $file['Title']);
    $this->assertTrue( $got_it, "MIMETest/TestMP3File: didn't find new file: " . $file["Title"]);
  }
  
  function TestHTMLFile() {
    
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    $file = array();
    $file['Title'] = "unit test " . rand(0, 10000) . ": HTML Upload";
    $file['Description'] = "description";
    $file['post_do_save'] = 1;
    $file['post_use_upload'] = 1;
    
    $this->Login();		
    $publish_url = get_base_url() . "publish.php";
    $upload = array();
    $u1 = array();
    $u1["key"] = "post_file_upload";
    $u1["content"] = file_get_contents("tests/testfile.html");
    $u1["filename"] = "testfile.html";
    $u1["mimetype"] = "text/html";
    $upload[] = $u1;
    
    $this->post( $publish_url, $file, $upload );
    $this->assertResponse("200", "MIMETest/TestHTMLFile: didn't get 200 response");		
    $this->assertWantedPattern("/mime_chooser/", "MIMETest/TestHTMLFile: expected file to fail but it didn't");
    $this->setField("mime_chooser", array("audio/unknown"));
    $this->clickImageById("publish_button");
    
    $this->assertResponse("200", "MIMETest/TestHTMLFile: didn't get 200 response");		
    
    global $store;
    $files = $store->getAllFiles();
    $got_it = $this->Find($files, "Title", encode($file['Title']));
    $this->assertTrue( $got_it, "MIMETest/TestHTMLFile: didn't find new file");
  }

}
?>