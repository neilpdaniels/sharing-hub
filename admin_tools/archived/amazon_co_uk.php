<?php
/**
 * 
 *   Amazon.co.uk
 *   last amended 18/04/07 - NPD
 * 
 */

$company_name = 'Amazon.co.uk';
$cfg_pre_price = addslashes('<td class="productLabel">Price:</td>

    <td><b class="price">£');

$cfg_post_price = addslashes('</b>');

$cfg_pre_quantity = addslashes('<b>Availability:</b> ');

$cfg_post_quantity = addslashes('. Dispatched from and sold by Amazon.co.uk.');

$cfg_payment_methods = "Debit/Credit card";

$cfg_preList = addslashes('<channel>');
$cfg_postList = addslashes('</channel>');
$cfg_preItem = addslashes('alt=');
$cfg_postItem = addslashes('heig');
?>