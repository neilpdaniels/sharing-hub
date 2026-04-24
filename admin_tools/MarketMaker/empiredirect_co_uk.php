<?php
/**
 * 
 *   empiredirect.co.uk
 *   last amended 22/07/07 - NPD
 * 
 */

$company_name = 'EmpireDirect.co.uk';
$cfg_pre_price = addslashes('<li id="price" visible="false"><b><span id="ctl00_mainContent_labPrice">&pound;');
$cfg_post_price = addslashes('</span></b>');
$cfg_pre_quantity = addslashes('id="ctl00_mainContent_lnkDeliveryMsg">');
$cfg_post_quantity = addslashes('</a>');
$cfg_payment_methods = "Debit/Credit card";
$cfg_pre_delivery = addslashes('<li class="del"><b>Delivery :</b> &pound;');
$cfg_post_delivery = addslashes('</li>');

$cfg_preList = addslashes('ctl00_mainContent_edProdList_divProdListContent');//<h2>Top Sellers</h2>';
$cfg_postList = addslashes('Customer Service | About Us');
$cfg_preItem = addslashes('Click here for more info on the>');
$cfg_postItem = addslashes('"><img');
?>