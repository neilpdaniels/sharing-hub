<?php
if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
}

 // if (isset($_SESSION['valid_user']) && $_SESSION['valid_user']==38){
  	
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
  	if(file_exists("../../include/objects/bosbo_category_products_class.php")){  	  	include "../../include/objects/bosbo_category_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){  	  	include "../../include/objects/bosbo_non_abstract_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	}
	
  
$allNACs = new Non_abstract_category(1);
$allNACs = $allNACs->getAllNACs();

 echo sizeof($allNACs) . " --- ";
/*
foreach ($allNACs as $value)
{
	echo "jj";
}*/
foreach ($allNACs as $value)
{
		//echo " " . $value . " ";
		$nac2 = new Non_abstract_category($value);
		$nac2 = $nac2->Get($value);
		$newItem = $nac2->getNewBestOffer();
		$usedItem = $nac2->getUsedBestOffer();
		/*
		if ($value == 596 ) {
			echo " BEFORE" . $lowestPrice;
		}
		*/
		if (is_numeric($newItem)&&is_numeric($usedItem)) {
			$lowestPrice = min($newItem, $usedItem);
		} elseif (is_numeric($newItem)) {
			$lowestPrice = $newItem;
		} elseif (is_numeric($usedItem)) {
			$lowestPrice = $usedItem;
		}
		/*if ($value == 596 ) {
			echo " newItem" . $newItem;
			echo " usedItem" . $usedItem;
		}
		*/
		//echo $lowestPrice . "  ";
		//delete the old order - maybe best to move to amend orders?
		$Database = new dbConnection();
		$query = "delete from `order` where `categoryid`='" . $value . "' and `userid`='38'";
		//echo $query;
		$Database->Query($query);
		if (!((!is_numeric($newItem)) && (!is_numeric($usedItem)))) {
		//save the order
			$expiry_date = mktime(23, 59, 59, 01, 01, 10);
			$total_price = round(($lowestPrice/100)*54, 2);
			
			// NEED TO SEND -1 for no image - these are default values so dont send if no image	
			$ord1 = new Order($value, 38, $total_price, 0, 0, '0', 'Debit/Credit card, Paypal, Personal Cheque', 'Bosbo.co.uk MarketMaker quote.', '1', '',$expiry_date, '1', '1', '-1', '', '', '');
		
			$newOrderId = $ord1->Save();
			echo $newOrderId . ", ";
					// set new Highs and lows
					//$nacat = new Non_abstract_category($_POST['category_id']);
					//$nacat->Get($_POST['category_id']);
					//$nacat->checkHighsAndLows();
		}
	}
//} echo "22:".$_SESSION['valid_user'];
?>