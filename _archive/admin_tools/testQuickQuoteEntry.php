<?php

  if (!isset($_SESSION)){

    session_name('bosbo-session');

    session_start();

  }


if(file_exists("php_spider/CURL.php")){	    include "php_spider/CURL.php"; }
if(file_exists("php_spider/bosbo_spider_class.php")) {      include "php_spider/bosbo_spider_class.php";  }
if(file_exists("../include/php_library_fns/db_functions.php")) {      include "../include/php_library_fns/db_functions.php";  }
if(file_exists("../include/php_library_fns/xml_functions.php")) {      include "../include/php_library_fns/xml_functions.php";  }
if(file_exists("../include/objects/bosbo_order_class.php")){	    include "../include/objects/bosbo_order_class.php";	  }
	


	$urlToTest = new CURL();
	$cfgFile = $_POST['companycfg'].".php";
	echo $cfgFile;
	if(file_exists($cfgFile)) {
		include($cfgFile);
			//echo "<br>1: " . $cfg_pre_price . "---" . $cfg_post_price . "---". $cfg_pre_quantity . "---" . $cfg_post_quantity;
				$prePrice = preg_replace ('/\s/', '', urldecode($cfg_pre_price));
				echo "<br>2: " . $prePrice;
				$postPrice = preg_replace ('/\s/', '', urldecode($cfg_post_price));
				$preQuantity = preg_replace ('/\s/', '', urldecode($cfg_pre_quantity));
				echo "<br>3: " . $preQuantity;
				$postQuantity = preg_replace ('/\s/', '', urldecode($cfg_post_quantity));
				echo "spidering item";
				$prePostage = preg_replace ('/\s/', '', urldecode($cfg_pre_postage));
				$postPostage = preg_replace ('/\s/', '', urldecode($cfg_post_postage));
				
		echo "VALID_USER: " . $_SESSION['valid_user'] . "<BR />";		// AUTO add affiliates
	if ($_SESSION['valid_user']==-9) {
		$url = "http://track.webgains.com/click.html?wgcampaignid=22640&wgprogramid=268&wgtarget=" . $_POST['url'];
	} elseif ($_SESSION['valid_user']==-4) {
		$url = "http://playcom.at/bosbo?DURL=" . $_POST['url'];
	} elseif ($_SESSION['valid_user']==-1) {
		$url = "http://www.amazon.co.uk/dp/" . $_POST['url'] . "/ref=nosim?tag=bosbo-21";
	} elseif ($_SESSION['valid_user']==-8) {
		$url = "http://affiliation.fotovista.com/track/click.php?bid=MTU2Ozc2MjY&desturl=" . $_POST['url'];
	} else {
		$url = $_POST['url'];
	}
	
				echo " | page URL: " . $url;
				$data = addslashes(preg_replace ('/\s/', '', $urlToTest->get(urldecode($url))));
				//$data = addslashes(preg_replace ('/\s/', '', $urlToTest->get($_POST['url'])));
				//echo "-------".$data."------";
				if ($data!='') {
					if (trim($prePrice)!=''&&trim($postPrice)!='') {
						
						$price = substr($data, (strpos($data, $prePrice)+strlen($prePrice)), -1);
						echo "1:".strlen($price);
						$price = substr($price, 0, strpos($price, $postPrice));
						
						//echo "<br /> | PRICE_1 = $price";
			
				if (strcmp($_POST['companycfg'], 'pixmania_co_uk') == 0) {
					// HACK for pixmainia_co_uk which uses images not numbers to display the price
					$price = str_replace('dot.gif', '_______', $price);
					$price = ereg_replace( '[^0-9_]+', '', $price);
					$price = str_replace('_______', '.', $price);
					$price = ereg_replace( '[^0-9.]+', '', $price);
				}
				$price = str_replace(",", "", $price);
				
						//ignore any preceeding pound sign in comparison as main spider does
						if (strcmp($price[0], "£")==0) {
							$price = substr($price, 1);
						}
						
						// checks item price (NOT p&p)
						echo "<br /> | PRICE = $price<br />";
						?>
						<input type="hidden" name="item_price" value="<?php echo $price; ?>">
						<?php
						
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
					
					if (trim($prePostage)!=''&&trim($postPostage)!='') {	
						$postage = substr($data, (strpos($data, $prePostage)+strlen($prePostage)), -1);
						$postage = substr($postage, 0, strpos($postage, $postPostage));
						echo "<br /> | POSTAGE = $postage";
					} else {
						echo "<br /> | NO_POSTAGE_SEARCH";
					}
		} else {
			echo "<br /> | NO CFG FILE FOUND";
		}
	} else {
		echo "<br /> | NO_WEBSITE";
	}
?>