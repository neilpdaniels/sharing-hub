<?php
/*
Author: Neil
Date: 17th Jan 2008

NOTES:  
this will go through each non abstract category, and see if we have any orders tthat have a vol>0 and are not expired.  if this is not the case, then the non_abstract catgory name is to be supplied to us in a table, which the admin user can then select to remove.  this will remove the non_abstract_category and abstract_category record, and should store the results in a file DELETE_PRODUCTS_<date>.html
*/

// standard includes - not optimised:
if(file_exists("../../include/php_library_fns/xml_functions.php")){    
	include "../../include/php_library_fns/xml_functions.php";}
if(file_exists("../../include/php_library_fns/db_functions.php")){ include "../../include/php_library_fns/db_functions.php";}
if(file_exists("../../include/php_library_fns/mkThumb.php")){      include "../../include/php_library_fns/mkThumb.php";}

  if(file_exists("../../include/objects/bosbo_category_class.php")){
    include "../../include/objects/bosbo_category_class.php";
  }
  if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){
    include "../../include/objects/bosbo_non_abstract_category_class.php";
  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){
    include "../../include/objects/bosbo_order_class.php";
  }
  // the database functions that this page uses
  if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {
      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";
  }
if (!isset($_SESSION)){
        session_name('bosbo-session');
        session_start();
}
?>
<FORM action="postToRemoveInactiveProducts.php" method="post">
<table width='100%' border='2'>
<?php
$all_non_abstract = new Non_abstract_category(0);
$ret_arr = $all_non_abstract->getAllNACs();
foreach ($ret_arr as $value)
{
        $temp_nac = new Non_abstract_category($value);
        $temp_nac = $temp_nac->Get($value);
	if (($temp_nac->getNewBestOffer()=="**.**")&&($temp_nac->getBestBid()=="**.**")) {
		$temp_ac = new Category();
		$temp_ac = $temp_ac->Get($value);
		// no active orders - show for deletion
		?>
		<tr>
			<td>
			<?php echo $temp_ac->getName(); ?>
			</td>
			<td>
			<input type='checkbox' name='<?php echo $value; ?>'
				value='<?php echo $value; ?>'
                                checked > 
			</td>
		</tr>
		<?php
	}
}
?>
</table>
<INPUT type="submit" value="Send">
</FORM>
<?php

?>
