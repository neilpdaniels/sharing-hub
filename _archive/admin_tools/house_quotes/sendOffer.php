<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
  $allValid = true;
  if (isset($_SESSION['valid_user'])){
  	
  	if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
	if(file_exists("../../include/php_library_fns/server_validation_functions.php")){    	include "../../include/php_library_fns/server_validation_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_order_class.php")){    	include "../../include/objects/bosbo_order_class.php";  	}
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){    	include "../../include/objects/bosbo_non_abstract_category_class.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
	/**
	 * CHECK ALL THE NECESSARY FIELDS HAVE BEEN SUPPLIED 
	 */
  	if (
  	(isset($_POST['condition']))&&(isset($_POST['quantity']))&&(isset($_POST['expiryDate']))&&(isset($_POST['totalPrice']))&&(isset($_POST['itemPrice']))&&(isset($_POST['pandpPrice']))&&(isset($_POST['insured']))&&(isset($_POST['payment_methods']))&&(isset($_POST['description']))&&(isset($_POST['picture']))&&(isset($_POST['picturethumb']))&&(isset($_POST['webAddress']))&&(isset($_POST['categoryId']))&&(isset($_POST['buy']))
  	) {
  		
		$userImageSupplied = true;
		if (
		((basename($_POST['picturethumb']))=='default.gif') 
		
		)
		{
			$userImageSupplied = false;
		}

		/** may need to unescape all then validate, then re-escape **/
		
		
  		/**
  		 * REMOVE BANNED WORDS
  		 */
  		$_POST['payment_methods'] = replaceBannedWords($_POST['payment_methods']);
  		$_POST['description'] = replaceBannedWords($_POST['description']);
  		
  		/**
  		 * VALIDATE ALL NECESSARY FIELDS
  		 */
  		
  		//temp vars for efficiency
  		$q=$_POST['quantity'];
  		//condition
  		if (!($_POST['condition']=='NEW' || $_POST['condition']=='USED')) {
  			$allValid = false;
  		//quantity
  		} elseif (!($q=='1'||$q=='2'||$q=='3'||$q=='4'||$q=='5'||$q=='6'|$q=='7'||$q=='8'||$q=='9'||$q=='&gt;9')) {
  			$allValid = false;
  		//expiry date
  		} elseif (!(ereg('[0-9][0-9][/][0-9][0-9][/][0-9][0-9]', $_POST['expiryDate']))) {
  			$allValid = false;
  		} elseif (!(checkdate(substr($_POST['expiryDate'], 3, 2), substr($_POST['expiryDate'], 0, 2), substr($_POST['expiryDate'], -2)))) {
  			$allValid = false;
  		//totalPrice
  		} elseif (!is_numeric($_POST['totalPrice'])) {
  			$allValid = false;
  		//itemPrice
  		} elseif (!is_numeric($_POST['itemPrice'])) {
  			$allValid = false;
  		//pandpPrice
  		} elseif (!is_numeric($_POST['pandpPrice'])) {
  			$allValid = false; 
  		//insured - YES or NO
  		} elseif (!($_POST['insured']=='not available' || (ereg('available for a premium of [&pound;]*[0-9]*.[0-9]*', $_POST['insured'])))) {
  			$allValid = false;
  		} elseif (!($_POST['insured']=='not available')) {
  			if (!is_numeric($_POST['insurancePrice'])) {
  				$allValid = false;  
  			}
  		//payment methods - length/ swear
  		} elseif (strlen($_POST['payment_methods'])>255 || strlen($_POST['payment_methods'])<1) {
  			$allValid = false;
  		//description - length/ swear
  		} elseif (strlen($_POST['description'])>255 || strlen($_POST['description'])<1) {
  			$allValid = false;
  		// image validation - just checkning they're on this server should prove sufficient
  		} elseif (!(ereg('images/user_images/[a-zA-Z0-9.:-_&=\"\'\\/]*', $_POST['picture']))) {
  			$allValid = false;
  		} elseif (!(ereg('images/user_images/[a-zA-Z0-9.:-_&=\"\'\\/]*', $_POST['picturethumb']))) {
  			$allValid = false;
  		// web address validation = address or -1 - may want to improve this, but dont want to catch stuff that js wont catch
  		} elseif (!(ereg('http://[a-zA-Z0-9.:-_&=\"\'\\/]*', $_POST['webAddress']) || $_POST['webAddress']=='-1')) {
  			$allValid = false;
  		}
  		if ($q=='&gt;9') {
  			// restricted to largest integer number (NOT 99999999999)
  			$_POST['quantity']=99999999999;
  		}
  		
  		//unset temp vars
  		unset($q);
  		
 		if ($allValid) {
		
		if ($_POST['condition']=='NEW') {
			$used = 0;
		} else {
			$used = 1;
		}
		
		if ($_POST['insured']=='not available') {
			$insurance = -1;
		} else {
			$insurance = $_POST['insurancePrice'];
		}
		
		$expiry_date = mktime(23, 59, 59, substr($_POST['expiryDate'], 3, 2), substr($_POST['expiryDate'], 0, 2), substr($_POST['expiryDate'], -2));

		// NEED TO SEND -1 for no image - these are default values so dont send if no image	
		$ord1 = new Order($_POST['categoryId'], $_SESSION['valid_user'], $_POST['totalPrice'],$_POST['itemPrice'], $_POST['pandpPrice'], $insurance, $_POST['payment_methods'], $_POST['description'], $used, '',$expiry_date, $_POST['buy'], $_POST['quantity'], $_POST['webAddress']);

		$newOrderId = $ord1->Save();
		if ($newOrderId==0) {
			// error executing Sql
			echo "<span id='small' align='center'>THERE HAS BEEN AN ERROR SUBMITTING YOUR ORDER</span>";
		} else {
		
			
			// set new Highs and lows
			$nacat = new Non_abstract_category($_POST['categoryId']);
			$nacat->Get($_POST['categoryId']);
			$nacat->checkHighsAndLows();
		
			//add images location
			if ($userImageSupplied) {
				//picture paths relative to THIS PAGE
				copy($_POST['picture'], '../../images/user_images/addOffer/'.$newOrderId.strstr(basename($_POST['picture']), "."));
				copy($_POST['picturethumb'], '../../images/user_images/addOffer/'.$newOrderId.'_thumb'.strstr(basename($_POST['picturethumb']), "."));
				//remove temporary pictures
				unlink($_POST['picture']);
				unlink($_POST['picturethumb']);
				//$ord2 = new Order();
				//$ord2 = $ord1->Get($newOrderId);	
				
				//picture path relative to ROOT PAGE
				$ord1->setpicturethumb('images/user_images/addOffer/'.$newOrderId.'_thumb'.strstr(basename($_POST['picturethumb']), "."));
				$ord1->setpicture('images/user_images/addOffer/'.$newOrderId.strstr(basename($_POST['picture']), "."));
				$ord1->Save();
			}
			
			/*
					$ord1 = new Order($_POST['categoryId'], $_SESSION['valid_user'], $_POST['totalPrice'],$_POST['itemPrice'], $_POST['pandpPrice'], $insurance, $_POST['payment_methods'], $_POST['description'], $used, '',$expiry_date, $_POST['buy'], $_POST['quantity'], $_POST['webAddress'], $_POST['picture'], $_POST['picturethumb'], '');*/
			
			
		
 			echo "<span id='small'><br/><br/>Your order has been successfully entered and is set to expire on ".
 			date('g:i:sa, l jS F Y', $expiry_date)
 			.".<br/><br/>Please use the below button to see your active order.</span>";
 			?>
 			<br/><br/>
 			<div align="center"><input type="button" value="Go to Live Product page" onClick="parent.location='../../navigation/<?php echo $nacat->getStaticProductPageName($nacat->getName()); ?>'"></div>
 			<?php

			}
 		} else  {
 			// vars are not all valid
 			echo "<span id='small' align='center'>HERE HAS BEEN AN ERROR SUBMITTING YOUR ORDER</span>";
 		}
  	} else {
  		//not all vars are supplied
  		echo "<span id='small' align='center'>THERE HAS BEEN AN ERROR SUBMITTING YOUR ORDER</span>";
  	}
  }
  else {
  	echo "you do not appear to be logged into Bosbo";
  }
?>