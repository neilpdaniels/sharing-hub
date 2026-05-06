<?php
if(file_exists("CURL.php")){        include "CURL.php"; }
if(file_exists("../php_spider/bosbo_spider_class.php")) {      include "../php_spider/bosbo_spider_class.php";  }
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {     include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){     include "../../include/objects/bosbo_order_class.php";  }



$USER_ID = -8;
$cfg_pre_price = addslashes('<h1 class="prd-price">£');
$cfg_post_price = addslashes('<span');

$cfg_pre_quantity = addslashes('<span class="prd-stock">');
$cfg_post_quantity = addslashes('
        </span>');

$cfg_payment_methods = "Debit/Credit card";

$cfg_pre_postage = addslashes("<strong>From&nbsp;£   ");
$cfg_post_postage = addslashes(" <span");

/**
 *
 * basic script that iterates through all spider_data records, grabbing the order records
 * if the order has a user_id matching USER_ID then the spider_data record is updated with
 * the information above
 *
 */


$spider_all = new Spider_data();
$tochange = $spider_all->get_all_links_for_user($USER_ID);
echo "SIZE OF : " . sizeof($tochange);

foreach ($tochange as $value) {
	$tempSpider = new Spider_data();
	$tempSpider = $tempSpider->Get($value);

	$tempSpider->SetPreprice($cfg_pre_price);
	$tempSpider->SetPostprice($cfg_post_price);
	$tempSpider->SetPrequantity($cfg_pre_quantity);
	$tempSpider->SetPostquantity($cfg_post_quantity);
	$tempSpider->SetPrepostage($cfg_pre_postage);
	$tempSpider->SetPostpostage($cfg_post_postage);

	$tempSpider = $tempSpider->Save();
}
?>
