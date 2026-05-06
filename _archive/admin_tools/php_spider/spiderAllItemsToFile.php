<?php

if(file_exists("CURL.php")){	    include "CURL.php"; }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }

/*if (isset($_GET['login'])&&isset($_GET['password'])) {
	$user1 = new User($_GET['login'],'','','','','','','','',$_GET['password'],'','', '');
	if($user1->AuthUser()){
		$user1 = $user1->GetByUsername($_GET['login']);
		$id = $user1->getUserId();
		if ($id<0) {
*/
$spider_all = new Spider_data();
if (isset($_GET['limit'])) {
	$to_spider = $spider_all->get_active_validated_links($_GET['limit']);
} else {
	$to_spider = $spider_all->get_active_validated_links();
}
shuffle($to_spider);

$to_report = array();
$number_to_spider = 0;




$myFile = "spiderResults.html";
$fh = fopen($myFile, 'w') or die("can't open file");
/**
 * 
 * PLAN : move toWriteBool to a few sections;
 * price only | quantity only | multiple - can just be strings
 * then sort by company
 * 
 */
$price_only_output = "";
$quantity_only_output = "";
$multiple_changes_output = "";

$price_int = 0;
$quantity_int = 0;

$toWriteData = "";
$toWriteBool = false;

$i = 0;

foreach ($to_spider as $value)
{
	fwrite($fh, "$i : ");
	$i++;
	//if ($i<10) {
	$price_int = 0;
	$quantity_int = 0;

	$toWriteBool = false;
	$toWriteData .= "<tr>";
	
	// for each validated URL
	$this_spider = new Spider_data();
	$this_spider->Get($value);
	$url = new CURL();
	$orderRecord = new Order();
	$orderRecord->Get($value);

	$this_spider->setLast_spidered(time());
	$this_spider->Save();
	
	$prePrice = preg_replace ('/\s/', '', $this_spider->preprice);
	$postPrice = preg_replace ('/\s/', '', $this_spider->postprice);
	$preQuantity = preg_replace ('/\s/', '', $this_spider->prequantity);
	$postQuantity = preg_replace ('/\s/', '', $this_spider->postquantity);
	$prePostage = preg_replace ('/\s/', '', $this_spider->prepostage);
	$postPostage = preg_replace ('/\s/', '', $this_spider->postpostage);
	
	$toWriteData .=  "<td width='20%'>Item:". $orderRecord->getorderId()."</td>";
	
	$data = preg_replace ('/\s/', '', $url->get($this_spider->url));
	
	
	if ($data!='') {
		if (trim($prePrice)!=''&&trim($postPrice)!='') {
			$price = substr($data, (strpos($data, $prePrice)+strlen($prePrice)), -1);
			$price = substr($price, 0, strpos($price, $postPrice));
			$price = str_replace(",", "", $price);
			
			
			// HACK for pixmainia_co_uk which uses images not numbers to display the price
			if ($orderRecord->getuserId() == -8 ) {
				// HACK for pixmainia_co_uk which uses images not numbers to display the price
					$price = str_replace('dot.gif', '_______', $price);
					$price = ereg_replace( '[^0-9_]+', '', $price);
					$price = str_replace('_______', '.', $price);
					$price = ereg_replace( '[^0-9.]+', '', $price);
			}
			
			
			//ignore any preceeding pound sign in comparison
			if (strcmp($price[0], "�")==0) {
				$price = substr($price, 1);
			}
			// checks item price (NOT p&p)
			if ($price != $orderRecord->getPrice())
			{
				
				$price_int = 1;
				$toWriteBool = true;
			  if (strlen($price)<70) {
				$toWriteData .= "<td width='70%'>PRICE_CHANGE: from ".$orderRecord->getPrice()." to $price </td>";

				$toWriteData .= "<td width='10%'> <input type='checkbox' name='" . $value . "'
				value='UPDATE `order` SET `price` =" . $price . ", `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'
				checked >
				change price
				</td>";

				
				$price_change = true;  // to be used when checking price/postage below
			  } else {
		    	$toWriteData .= "<td width='70%'>PRICE_CHANGE: from ".$orderRecord->getPrice()." to TOO_LARGE </td>";
		    	
		    	$toWriteData .= "<td>&nbsp;</td>";
		    	
  			  }
			} else
			{
				$toWriteData .= "<td width='70%'>NO_PRICE_CHANGE: from ".$orderRecord->getPrice()."</td>";

				$toWriteData .= "<td width='10%'>&nbsp;</td>";			  

			}
			$toWriteData .=  "</tr>";
			
/*
-7  //comet_co_uk
-5 	//empiredirect_co_uk
-4 	//play_com
-3 	//rankhour_com
-2 	//tecno_co_uk
-1, 15.00,  	//amazon_co_uk
*/
			switch ($orderRecord->getuserId()) {
				case -1:
					if ($price_change) {
							if ($price<15 && $orderRecord->getPostage()==0) {
							$toWriteData .=  "<tr><td width='100%'>";
			
							$toWriteData .=  "price is < �15 but postage is free<br />";
			
							$toWriteData .=  "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 3.23, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .=  "</td></tr>";	
					    	
						} elseif ($price>15 && $orderRecord->getPostage()!=0) {
							$toWriteData .=  "<tr><td width='100%'>";
			
							$toWriteData .=  "price is > �15 but postage is NOT free<br />";
			
							$toWriteData .=  "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .=  "</td></tr>";							
					    	
						}
					} else {
						if ($orderRecord->getPrice()<15 && $orderRecord->getPostage()==0) {
							$toWriteData .=  "<tr><td width='100%'>";
			
							$toWriteData .=  "price is < �15 but postage is free<br />";
			
							$toWriteData .=  "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 3.23, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .=  "</td></tr>";	
					    	
						} elseif ($orderRecord->getPrice()>15 && $orderRecord->getPostage()!=0) {
							$toWriteData .=  "<tr><td width='100%'>";
			
							$toWriteData .=  "price is > �15 but postage is NOT free<br />";
			
							$toWriteData .=  "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";							
					    	
						}
					}
				    break;
				case -3:
					if ($price_change) {
						if ($price<200 && $orderRecord->getPostage()==0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is < �200 but postage is free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 5.99, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";	
					    	
						} elseif ($price>200 && $orderRecord->getPostage()!=0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is > �200 but postage is NOT free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";							
					    	
						}
					} else {
						if ($orderRecord->getPrice()<200 && $orderRecord->getPostage()==0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is < �200 but postage is free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 5.99, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
					    	
					    	$toWriteData .= "</td></tr>";	
					    	
						} elseif ($orderRecord->getPrice()>200 && $orderRecord->getPostage()!=0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is > �200 but postage is NOT free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";							
					    	
						}
					}
				    break;
				case -6:
					if ($price_change) {
						if ($price<99 && $orderRecord->getPostage()==0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is < �99 but postage is free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 3.95, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";	
					    	
						} elseif ($price>99 && $orderRecord->getPostage()!=0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is > �99 but postage is NOT free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";							
					    	
						}
					} else {
						if ($orderRecord->getPrice()<99 && $orderRecord->getPostage()==0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is < �99 but postage is free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 3.95, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";	
					    	
						} elseif ($orderRecord->getPrice()>99 && $orderRecord->getPostage()!=0) {
							$toWriteData .= "<tr><td width='100%'>";
			
							$toWriteData .= "price is > �99 but postage is NOT free<br />";
			
							$toWriteData .= "<input type='text' size='150' name='" . $value . "_post' value='UPDATE `order` SET `postage` = 0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'>";
			
					    	$toWriteData .= "</td></tr>";
					    	
						}
					}
				    break;    
			}
		} else {
			$toWriteData .= "<td width='80%'>NO_PRICE_SEARCH </td>";
			
			$toWriteData .= "</tr>";
			
		}
		
		$toWriteData .= "<tr><td width='20%'>&nbsp;</td>";
		
		if (trim($preQuantity)!=''&&trim($postQuantity)!='') {
			$quantity = substr($data, (strpos($data, $preQuantity)+strlen($preQuantity)), -1);
			$quantity = substr($quantity, 0, strpos($quantity, $postQuantity));
			if (!(($quantity == $orderRecord->getvolumeasint()) || (strcmp(trim(strtolower($quantity)), 'instock') == 0)
			|| (strcmp(trim(strtolower($quantity)), 'orderbeforenoonfornextworkingdaydelivery') == 0) 
			|| (strcmp(trim(strtolower($quantity)), 'instockforhomedelivery') == 0)
			|| (strcmp(trim(strtolower($quantity)), 'instock-usuallydespatchedwithin24hours') == 0)
			))
			{
				
				$quantity_int = 1;
				$toWriteBool = true;
			  if (strlen($quantity)<120) {
				$toWriteData .= "<td width='70%'>QUANTITY_CHANGE: from ".$orderRecord->getvolumeasint()." to $quantity</td>";

			  } else {
			    $toWriteData .= "<td width='70%'>QUANTITY_CHANGE: from ".$orderRecord->getvolumeasint()." to TOO_LARGE </td>";
			    
			  }
				$toWriteData .= "<td width='10%'>
				<INPUT TYPE='radio' name='". $value . "_quan'
				value='UPDATE `order` SET `volume` =9999999, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'
				>full quantity<BR />
				<INPUT TYPE='radio' name='". $value . "_quan'
				value='UPDATE `order` SET `volume` =0, `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1' checked
				>zero quantity<BR />
				<INPUT TYPE='checkbox' name='disable_' 
				value='UPDATE `spider_data` SET `active` =0 WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'
				>disable</td>";

			} else {
			  	$toWriteData .= "<td width='70%'>NO_QUANTITY_CHANGE: from ".$orderRecord->getvolumeasint()."</td>";
			  	
				$toWriteData .= "<td width='10%'>&nbsp;</td>";		

			}
		} else {
			$toWriteData .= "<td width='80%'>NO_QUANTITY_SEARCH </td>";
			
		}
		$toWriteData .= "<tr>";
		

		$toWriteData .= "<tr><td width='20%'>&nbsp;</td>";
		
		if (trim($prePostage)!=''&&trim($postPostage)!='') {
			$postage = substr($data, (strpos($data, $prePostage)+strlen($prePostage)), -1);
			$postage = substr($postage, 0, strpos($postage, $postPostage));
			if (!(($postage == $orderRecord->getPostage())))
			{
				$toWriteBool = true;
			  if (strlen($postage)<120) {
				$toWriteData .= "<td width='70%'>POSTAGE_CHANGE: from ".$orderRecord->getPostage()." to $postage</td>";

			  } else {
			    $toWriteData .= "<td width='70%'>POSTAGE_CHANGE: from ".$orderRecord->getPostage()." to TOO_LARGE </td>";
			    
			  }
				$toWriteData .= "<td width='10%'> <input type='checkbox' name='" . $value . "'
				value='UPDATE `order` SET `price` =" . $price . ", `enteredtime` = NOW( ) WHERE `orderid` = ". $orderRecord->getorderId() ." LIMIT 1'
				checked >
				change postage
				</td>";

			} else {
			  	$toWriteData .= "<td width='70%'>NO_POSTAGE_CHANGE: from ".$orderRecord->getPostage()."</td>";
				$toWriteData .= "<td width='10%'>&nbsp;</td>";		

			}
		} else {
			$toWriteData .= "<td width='80%'>NO_POSTAGE_SEARCH </td>";
			
		}
		$toWriteData .= "<tr>";
		

	$toWriteData .= "<tr><td colspan='3'>URL: <a href='" . $this_spider->url . "'>" . $this_spider->url . "</a></td></tr>";	
	
	} else {
	$toWriteData .= "	<tr><td colspan='3'>URL: NO_WEBSITE</td></tr>";	
	
	}
	$toWriteData .= "<tr><td colspan='3' BGCOLOR='#ffff00'>&nbsp;</td></tr>";
	
	sleep (2);

	if ($toWriteBool) {
		if ($price_int==1 && $quantity_int==0) {
			$price_only_output .= $toWriteData;
		} elseif ($price_int==0 && $quantity_int==1) {
			$quantity_only_output .= $toWriteData;
		} else {
			$multiple_changes_output .= $toWriteData;			
		}
	}
	$toWriteData = "";
}
	//}	////////////////////////////////////////////


// write all data to file	
$stringToAdd = '</table>
<INPUT type="submit" value="Send">
</FORM><br /><br />';

fwrite($fh, '<FORM action="postToSpiderAllItemPrices.php" method="post">');
fwrite($fh, "<table width='100%' border='2'>");
fwrite($fh, $price_only_output);
fwrite($fh, $stringToAdd);

fwrite($fh, '<FORM action="postToSpiderAllItemPrices.php" method="post">');
fwrite($fh, "<table width='100%' border='2'>");
fwrite($fh, $quantity_only_output);
fwrite($fh, $stringToAdd);

fwrite($fh, '<FORM action="postToSpiderAllItemPrices.php" method="post">');
fwrite($fh, "<table width='100%' border='2'>");
fwrite($fh, $multiple_changes_output);
fwrite($fh, $stringToAdd);

/*		} else {
			echo "ERROR1";
		}
	} else {
		echo "ERROR2";
	}
} else {
	echo "ERROR3";
}
*/
// compile report (& email? - when cronned)


fclose($fh);
?>
