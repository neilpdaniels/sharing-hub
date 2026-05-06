<?php
if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
}

  if (isset($_SESSION['valid_user']) && $_SESSION['valid_user']<0){
  	
  	if(file_exists("../include/php_library_fns/db_functions.php")){    	include "../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../include/objects/user_functions.php")){    	include "../include/objects/user_functions.php";  	}
	if(file_exists("../include/php_library_fns/xml_functions.php")){    	include "../include/php_library_fns/xml_functions.php";  	}
	if(file_exists("../include/php_library_fns/server_validation_functions.php")){    	include "../include/php_library_fns/server_validation_functions.php";  	}
  	if(file_exists("../include/objects/bosbo_order_class.php")){    	include "../include/objects/bosbo_order_class.php";  	}
  	if(file_exists("../include/objects/bosbo_non_abstract_category_class.php")){    	include "../include/objects/bosbo_non_abstract_category_class.php";  	}
  	if(file_exists("../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
	  if(file_exists("../include/objects/bosbo_message_class.php")){	    include "../include/objects/bosbo_message_class.php";  }
	if(file_exists("php_spider/bosbo_spider_class.php")) {      include "php_spider/bosbo_spider_class.php";  }
	
  
    $cfgFile = $_POST['companies'].".php";
	if(file_exists($cfgFile)) {
		echo "<br>file is being included<br>";
		include($cfgFile);
	}
  
  
//save the order
	$expiry_date = mktime(23, 59, 59, 01, 01, 10);
	$total_price = $_POST['item_price'] + $_POST['pandp'];
	
	// AUTO add affiliates
	if ($_SESSION['valid_user']==-9) {
		$url = "http://track.webgains.com/click.html?wgcampaignid=22640&wgprogramid=268&wgtarget=" . $_POST['url'];
	} elseif ($_SESSION['valid_user']==-4) {
		$url = "http://playcom.at/bosbo?DURL=" . $_POST['url'];
	} elseif ($_SESSION['valid_user']==-1) {
		$url = "http://www.amazon.co.uk/dp/" . $_POST['url'] . "/ref=nosim?tag=bosbo-21";
	} elseif ($_SESSION['valid_user']==-8) {
		$url = "http://affiliation.fotovista.com/track/click.php?bid=MTU2Ozc2MjY&desturl=" . $_POST['url'];
	} elseif ($_SESSION['valid_user']==-11) {
		$url = "http://track.webgains.com/click.html?wgcampaignid=22640&wgprogramid=245&wgtarget=" . $_POST['url'];
	} else {
		$url = $_POST['url'];
	}
	
	// NEED TO SEND -1 for no image - these are default values so dont send if no image	
	$ord1 = new Order($_POST['category_id'], $_SESSION['valid_user'], $total_price, $_POST['item_price'], $_POST['pandp'], '1', $cfg_payment_methods, 'see website', '0', '',$expiry_date, '0', '9999999', $url, '', '', $company_name);

	$newOrderId = $ord1->Save();
			// set new Highs and lows
			$nacat = new Non_abstract_category($_POST['category_id']);
			$nacat->Get($_POST['category_id']);
			$nacat->checkHighsAndLows();
			
//save the spider data
		$spider = new Spider_data(
		$newOrderId,
		$url,
		1,
		1,
		$cfg_pre_price,
		$cfg_post_price,
		$cfg_pre_quantity,
		$cfg_post_quantity,
		'',
		$cfg_pre_postage,
		$cfg_post_postage);
		$spider_res = $spider->Save();

		?>
		<a href="../">main page</a><br />
		<a href="../pages/navigation/product_page.php?category_id=<?php echo $_POST['category_id']; ?>">Product page</a>
		<?php

  }
?>