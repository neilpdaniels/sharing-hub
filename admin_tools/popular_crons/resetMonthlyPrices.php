<?php

/* resetMonthlyPrices just iterates through the non_abstract_categories calling the resetMonthlyPrices function for eacch */

// standard includes - not optimised:
if(file_exists("../../include/php_library_fns/xml_functions.php")){        include "../../include/php_library_fns/xml_functions.php";}
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

$all_non_abstract = new Non_abstract_category(0);
$ret_arr = $all_non_abstract->getAllNACs();
echo sizeof($ret_arr);
foreach ($ret_arr as $value)
{
	$temp_nac = new Non_abstract_category($value);
	$temp_nac->Get($value);
	$temp_nac->resetMonthlyPrices();
	$temp_nac->Save();
	echo "RESET : ";
}
?>
