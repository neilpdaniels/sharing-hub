<?php
/**'preprice='+document.forms['addspider'].elements['preprice'].value
+'&postprice='+document.forms['addspider'].elements['postprice'].value
+'&prequantity='+document.forms['addspider'].elements['prequantity'].value
+'&postquantity='+document.forms['addspider'].elements['postquantity'].value
**/


if(file_exists("php_spider/CURL.php")){	    include "php_spider/CURL.php"; }
if(file_exists("php_spider/bosbo_spider_class.php")) {      include "php_spider/bosbo_spider_class.php";  }
if(file_exists("../include/php_library_fns/db_functions.php")) {      include "../include/php_library_fns/db_functions.php";  }
if(file_exists("../include/php_library_fns/xml_functions.php")) {      include "../include/php_library_fns/xml_functions.php";  }
if(file_exists("../include/objects/bosbo_order_class.php")){	    include "../include/objects/bosbo_order_class.php";	  }
	
	$urlToTest = new CURL();
	$prePrice = preg_replace ('/\s/', '', urldecode($_POST['preprice']));
	$postPrice = preg_replace ('/\s/', '', urldecode($_POST['postprice']));
	$preQuantity = preg_replace ('/\s/', '', urldecode($_POST['prequantity']));
	$postQuantity = preg_replace ('/\s/', '', urldecode($_POST['postquantity']));
	echo "spidering item";
	echo " | page URL: " . $_POST['url'];
	$data = addslashes(preg_replace ('/\s/', '', $urlToTest->get(urldecode($_POST['url']))));
	if ($data!='') {
		if (trim($prePrice)!=''&&trim($postPrice)!='') {
			
			$price = substr($data, (strpos($data, $prePrice)+strlen($prePrice)), -1);
			echo "1:".strlen($price);
			$price = substr($price, 0, strpos($price, $postPrice));
			echo "2:".$price;
			//ignore any preceeding pound sign in comparison as main spider does
			if (strcmp($price[0], "£")==0) {
				$price = substr($price, 1);
			}
			
			// checks item price (NOT p&p)
			echo "<br /> | PRICE = $price";
			
		} else {
			echo "<br /> | NO_PRICE_SEARCH";
		}
		if (trim($preQuantity)!=''&&trim($postQuantity)!='') {
			
			$quantity = substr($data, (strpos($data, $preQuantity)+strlen($preQuantity)), -1);
			$quantity = substr($quantity, 0, strpos($quantity, $postQuantity));
			echo "<br /> | QUANTITY = $quantity";
		} else {
			echo "<br /> | NO_QUANTITY_SEARCH";
		}
	} else {
		echo "<br /> | NO_WEBSITE";
	}
?>