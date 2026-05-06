<?php
// Pull in PHP Simple HTML DOM Parser
include("./simple_html_dom.php");

// Settings on top
$sitesToCheck = array(
					// id is the page ID for selector
					array("url" => "http://www.arsenal.com/first-team/players", "selector" => "#squad"),
					array("url" => "http://www.liverpoolfc.tv/news", "selector" => "ul[style='height:400px;']")
				);
$savePath = "./";
$emailContent = "";

// For every page to check...
foreach($sitesToCheck as $site) {
	$url = $site["url"];
	
	// Calculate the cachedPage name, set oldContent = "";
	$fileName = md5($url);
	$oldContent = "";
	
	// Get the URL's current page content
	$html = file_get_html($url);
	
	// Find content by querying with a selector, just like a selector engine!
	foreach($html->find($site["selector"]) as $element) {
		echo $element->plaintext;;
	}
	
	// Build simple email content
$emailContent = "David, the following page has changed!\n\n".$url."\n\n";
	
}
	echo $emailContent;
?>
