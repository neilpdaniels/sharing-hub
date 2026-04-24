<?php
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
  	if(file_exists("../../include/objects/bosbo_category_products_class.php")){  	  	include "../../include/objects/bosbo_category_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_most_popular_products_class.php")){  	  	include "../../include/objects/bosbo_most_popular_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){  	  	include "../../include/objects/bosbo_non_abstract_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php"; }
  
  
	$categoryList = Array();
	$Database = new dbConnection();
	$query = "SELECT * FROM `most_popular_products` WHERE `abstract_category_id`=1";
	$Database->Query($query);
	for ($i=0; $i < $Database->Rows(); $i++)
	{
		$first = $Database->unescape($Database->Result($i, "first"));
		$second = $Database->unescape($Database->Result($i, "second"));
		$third = $Database->unescape($Database->Result($i, "third"));
		$forth = $Database->unescape($Database->Result($i, "forth"));
		$fifth = $Database->unescape($Database->Result($i, "fifth"));
		$sixth = $Database->unescape($Database->Result($i, "sixth"));
		$seventh = $Database->unescape($Database->Result($i, "seventh"));
		$eighth = $Database->unescape($Database->Result($i, "eighth"));
		$nineth = $Database->unescape($Database->Result($i, "nineth"));
		$tenth = $Database->unescape($Database->Result($i, "tenth"));
		$cat_obj = new Category();
		$cat_obj = $cat_obj->Get($first);
		$openNACat = new Non_abstract_category($first);
		$openNACat = $openNACat->Get($first);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
		$cat_obj = $cat_obj->Get($second);
		$openNACat = $openNACat->Get($second);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
		$cat_obj = $cat_obj->Get($third);
		$openNACat = $openNACat->Get($third);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
		$cat_obj = $cat_obj->Get($forth);
		$openNACat = $openNACat->Get($forth);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
		$cat_obj = $cat_obj->Get($fifth);
		$openNACat = $openNACat->Get($fifth);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
		$cat_obj = $cat_obj->Get($sixth);
		$openNACat = $openNACat->Get($sixth);
		echo "<li><a href='<?php echo \$address; ?>".$openNACat->getStaticProductPageName($cat_obj->getName())."'>".$cat_obj->getName()."</a></li><li>&nbsp;</li>";
	}
?>