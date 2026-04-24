<?php
if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
/**
 
orderid
*url
validrobot
active
*preprice
*postprice
*prequantity
*postquantity 
 
 */

echo $_SESSION['valid_user']."--".$_GET['order_id']."++";
if (isset($_SESSION['valid_user']) && isset($_GET['order_id'])){
	if ($_SESSION['valid_user']<0) {
		?>
		
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Register</title>

	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="ajax_admin_functions.js"></script>
<!--	<script type="text/javascript" src="../js/javascript_functions.js"></script>	-->
</head>

<body>



<form name="addspider" method="POST" action="send_convert_to_house_quote.php"><?php // echo $_SERVER['PHP_SELF']; ?>
	url: <input type="text" name="url" size="100" /><br/>
	preprice: <textarea name="preprice"  cols="100" rows="4" /></textarea><br/>
	postprice: <textarea name="postprice"  cols="100" rows="4" /></textarea><br/>
	prequantity: <textarea name="prequantity"  cols="100" rows="4" /></textarea><br/>
	postquantity: <textarea name="postquantity"  cols="100" rows="4" /></textarea><br/>
	onbehalfof: <input type="textarea" name="onbehalfof" size="100" /><br/>
	<input type="hidden" name="order_id" value="<?php echo $_GET['order_id']; ?>">
	<input type="submit" value="Submit"/>
</form>
<br>
	              <input type="button" name="test" value="Test"  onClick="
alert('testing');
postContent('testHouseOrderDetails.php', 
'url='+escape(document.forms['addspider'].elements['url'].value)
+'&preprice='+escape(document.forms['addspider'].elements['preprice'].value)
+'&postprice='+escape(document.forms['addspider'].elements['postprice'].value)
+'&prequantity='+escape(document.forms['addspider'].elements['prequantity'].value)
+'&postquantity='+escape(document.forms['addspider'].elements['postquantity'].value)
);"><br>
<div id="testResults"></div>
		<?php
	} else {
		echo "ERROR1";
	}
} else {
	echo "ERROR2";
}
?>
</body>
</html>