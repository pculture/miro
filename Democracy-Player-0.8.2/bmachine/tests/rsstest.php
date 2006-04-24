<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

include_once("publishing.php");

class RSSTest extends BMTestCase {

  function RSSTest() {
  }

  function TestGenerateRSS() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
	
    global $store;
    global $rss_dir;

    $this->Login();

    $channel_id = $store->addNewChannel( "Junky Channel" );
    $channel = $store->getChannel($channel_id);
    $channel["OpenPublish"] = 1;
    $store->saveChannel($channel);
	
    $file = array();
    set_file_defaults($file);
    
    $file['URL'] = "http://lovelylittlegirls.com/z/fluvial-origine_des_femmes.mp3";
    $file['Title'] = "RSS File & Junk Test";
    $file['Description'] = "URL desc";
    $file['donation_id'] = 1;
    $file['People'] = array(
			    0 => "colin:did stuff & had fun",
			    1 => "colin2:did other stuff & slept a lot",
    );
    $file['Keywords'] = array(
			      0 => 'kw1',
			      1 => 'kw2');

    $file['post_channels'] = array($channel_id);
    
    assert( publish_file($file) );

    $rss_url = get_base_url() . "rss.php?i=" . $channel_id . "&amp;force=1";
    $test_url = "http://www.feedvalidator.org/check.cgi?url=" . $rss_url;
    
    $this->get($test_url);
    $this->assertWantedPattern('/Congratulations/i', $rss_url);


    $channels = $store->getAllChannels();
	
    foreach($channels as $channel) {
      makeChannelRss($channel["ID"]);
      $this->assertTrue(file_exists("$rss_dir/" . $channel["ID"] . ".rss"), "Didn't generate " . $channel["ID"] . ".rss" );			
    }
  }

  function TestValidateRSS() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    global $store;
    $channels = $store->getAllChannels();
    
    foreach($channels as $channel) {
      $rss_url = get_base_url() . "rss.php?i=" . $channel["ID"] . "&amp;force=1";
      $test_url = "http://www.feedvalidator.org/check.cgi?url=" . urlencode($rss_url);

      $this->get($test_url);

      $content = $this->_browser->getContent();
      eregi("^(.*)(<[ \\n\\r\\t]*ul(>|[^>]*>))(.*)(<[ \\n\\r\\t]*/[ \\n\\r\\t]*ul(>|[^>]*>))(.*)$", $content, $errors);
      //      preg_match('/<span class="message">(.*?)<\/span>/', $content, $errors);
      //preg_match('/<span class="message">(.*?)<\/span>/', $content, $errors);
      //print $content . "\n\n\n";
      //      print_r($errors);
      //$details = strip_tags($errors[4]);
      $details = $errors[4];
      $details = str_replace("&nbsp;", " ", $details);
      $details = str_replace("&gt;", ">", $details);
      $details = str_replace("&lt;", "<", $details);
      $this->assertWantedPattern('/Congratulations/i', $rss_url . $details );
    }
  }
}
?>