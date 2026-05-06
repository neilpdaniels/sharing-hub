<?php
if (!isset($_SESSION)){

    session_name('bosbo-session');

    session_start();

}

if(file_exists("CURL.php")){	    include "CURL.php"; }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
if(file_exists("../../include/objects/bosbo_most_popular_products_class.php")){     include "../../include/objects/bosbo_most_popular_products_class.php";        }
if(file_exists("../../include/objects/user_functions.php")){    include "../../include/objects/user_functions.php";  }
if(file_exists("../../include/objects/bosbo_affiliate_popular_products_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_class.php";  }
if(file_exists("../../include/php_library_fns/search_functions.php")) {      include "../../include/php_library_fns/search_functions.php";  }
if(file_exists("../../include/objects/bosbo_category_class.php")){    include "../../include/objects/bosbo_category_class.php";  }
if(file_exists("../../include/objects/bosbo_affiliate_popular_products_ignore_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_ignore_class.php";  }
///if(file_exists("../../include//objects/bosbo_affiliate_popular_products_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_class.php";  }
?>
<html>
  <head>

    <title>Bosbo</title>

    <link rel="stylesheet" type="text/css" href="../../css/style.css" />

    <link rel="stylesheet" type="text/css" href="../../css/navigation.css" />

	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></SCRIPT>

	<script type="text/javascript" src="../../ajax/ajax_admin_functions.js"></script>

	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>

  </head>
  <body>
<?php
/*
  16th Feb 2008.  Neil Daniels
  This file allows a way for affilite/admin users (<0) to add their best sellers
  lists to the affiliate_popular_products table of the db.

  the only parameter DEFINITELY required for entry is the location of the bestsellers list
  ; the user can be taken from the current session.  an ajax test of this (such as that for
  quick order entry MAY be added for ease of use.
*/
echo $_GET['node'];
echo $_GET['bestseller_add'];
echo $_SESSION['valid_user'];

?>
<table width='100%' border='1'>
<?php
echo "<tr>";

// get user details and load correct cfg file:
	$userid = $_SESSION['valid_user'];  //needed to extract cfg file.
	$categoryid = $_GET['node'];
	$list_webpage = $_GET['bestseller_add'];
	$tempUser = new User();
	$tempUser = $tempUser->Get($userid);
	$username = $tempUser->getUserName();
	$cfgFile = "../".$username.".php";
	if(file_exists($cfgFile)) {
      		include($cfgFile);
      		//echo "| 1: " . $_GET['bestseller_add'];
	}
	//echo "| 2: " . $_GET['bestseller_add'];

	// display info about current search;
	$categ = new Category($categoryid);
	$categ = $categ->get($categoryid);
	echo "<td width='50%'>AFFILIATE: ".$username. "</td>";
	echo "<td width='50%'>CATEGORY: ".$categ->getName()."</td>";
	
	// source webpage:
	$url = new CURL();
	$list_webpage = preg_replace ('/\s/', '', $list_webpage);
	//echo "---" . $_GET['bestseller_add'];
	//preg_replace ('/\s/', '', 
	$data = $url->get($_GET['bestseller_add']);

	//$data = addslashes($url->get($_GET['bestseller_add']));
	
	//echo "---" . sizeof($data);
	// work for hardcoded, local example before uncommenting above.
//$myFile = "playbestseller.html";
 //	if (file_exists($myFile)) {
	//	$data = addslashes(file_get_contents($myFile));
		//echo "sizeof - " . sizeof($data) . "  -- " . $data;
	//}
	//$prePrice = preg_replace ('/\s/', '', $this_spider->preprice);
//echo stripslashes($data);

	// extract complete list using same substr as below
	// this will remove all before pre and all after post
	$preList = $cfg_preList;
	$postList = $cfg_postList;
	//$preList = preg_replace ('/\s/', '', $preList);
	//$postList = preg_replace ('/\s/', '', $postList);

        if ($data!='') {
                if (trim($preList)!=''&&trim($postList)!='') {
                        $data = substr($data, (strpos($data, $preList)+strlen($preList)), -1);
			$data = substr($data, 0, strpos($data, $postList));
                }
        }

	//echo stripslashes($data);
        
	// extract individual products using a different method
	// proposition is while (if pre exists, if post exists after pre trim original
	// string until after 1st occurance of post and treat pre->post
	// as one example... may need to employ STRICT REG EXPS
	$results_arr = Array();
	$preItem = $cfg_preItem;
	$postItem = $cfg_postItem;
	while((strpos($data, $preItem) !== false) && (strpos($data, $postItem)!== false)) {
		$tempItem = substr($data, (strpos($data, $preItem)+strlen($preItem)), -1);
		$tempItem = substr($tempItem, 0, strpos($tempItem, $postItem));
		//$data = substr($data, (strpos($data, $postItem)+strlen($postItem)), -1);
		//$data = substr($data, (strpos($data,
		// $tempItem)+strlen($tempItem)+strlen($postItem)), -1);
		$data = stripslashes(stristr($data, $tempItem));
		//$data = str_replace('"',' ',stristr($data, $tempItem));
		array_push($results_arr, $tempItem);
	}

	// compare these to the catalogue
	foreach ($results_arr as $value)
	{
		// check we've no match or ignore in the database table:
		//exists_for_name
		$ignore_check = new affiliate_popular_products_ignore();
		if (!$ignore_check->exists_for_name($value))
		{
			$value = str_replace("\"","",$value);
			$value = str_replace("\'","",$value);
			echo "<tr><td colspan='2'>";
			echo "<DIV id='".md5($value)."'><table><tr><td>".$value."</td></tr>";
			$completeResults = searchForString($value, '', 12, '');
			$productsFound   = array_pop($completeResults);
			$categoriesFound = array_pop($completeResults);
			$count = array_shift($productsFound);
			echo "<tr><td><FORM name='". md5($value) ."'><select name='results'>";
			foreach ($productsFound as $product_value)
			{
				// could use $product_value[1] for the name:
				$product = new Category($product_value[0]);
				$product = $product->get($product_value[0]);
				echo "<option value='".$product_value[0]."'>".$product->getName()."</option>";
			}
			echo "</select>";
			echo "<select name='decision'>";
			echo "<option value='UNSURE'>UNSURE</option>";
			echo "<option value='IGNORE'>IGNORE</option>";
			echo "<option value='MATCH'>MATCH</option>";
			echo "<option value='ALERT'>ALERT</option>";
			echo "</select>";
			echo "<input type='hidden' name='product_name' value='".$value."'>";
			// NEXT SECTION - THIS SHOULD DO AN AJAX SUBMIT OF THE CHOSEN VALUES.
			// THESE WILL BE STORED IN THE DB, AND THE DIV REPLACED WITH
			// "STORED: MATCH" OR THE LIKE
			//  type='submit'  
			?>
			<input type="button" value='store' onclick="alert('neil');
			postSaveAff('spider_AJAX_fns/postSaveAffiliateIgnore.php',
			 <?php echo "'". md5($value) ."'"; ?>,
'product_name='+document.forms['<?php echo md5($value); ?>'].elements['product_name'].value
+'&decision='+document.forms['<?php echo md5($value); ?>'].elements['decision'].value
+'&categoryid='+document.forms['<?php echo md5($value); ?>'].elements['results'].value
+'&userid=<?php echo $userid; ?>'
+'&list_webpage=<?php echo $list_webpage; ?>'
);
			">
			
			
			<?php
			echo "</FORM></td></tr></table></div>";
			echo "</td></tr>";
		}
	}
echo "</tr>";
echo "</table>";

// BUTTON TO SAVE
?>
<input type="button" value="Add bestsellers list!" onClick="parent.location='../php_spider/postLinkToBestSellersList.php?node=<?php echo $_GET['node']; ?>&bestseller_add=<?php echo $_GET['bestseller_add']; ?>"></form></div>