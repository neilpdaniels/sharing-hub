<?php
if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
}

if (isset($_SESSION['valid_user']) && isset($_GET['category_id'])){
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



<form name="addspider" method="POST" action="sendQuickQuoteEntry.php"><?php // echo $_SERVER['PHP_SELF']; ?>
	url: <input type="text" name="url" size="100" /><br/>
	company: <br />
	<select name="companies">
		<option value="amazon_co_uk">amazon_co_uk</option>
		<option value="play_com">play_com</option>
		<option value="rankhour_com">rankhour_com</option>
		<option value="tecno_co_uk">tecno_co_uk</option>
		<option value="empiredirect_co_uk">empiredirect_co_uk</option>
		<option value="jessops_com">jessops_com</option>
		<option value="comet_co_uk">comet_co_uk</option>
		<option value="pixmania_co_uk">pixmania_co_uk</option>
		<option value="cheaptelly_co_uk">cheaptelly_co_uk</option>
		<option value="apollo2000_co_uk">apollo2000_co_uk</option>
		<option value="duck_co_uk">duck_co_uk</option>
		<option value="blahDVD_co_uk" selected>blahDVD_co_uk</option>
	</select>
	P&amp;p: <input type="text" name="pandp" size="100" /><br/>
	<input type="hidden" name="category_id" value="<?php echo $_GET['category_id']; ?>">

<div id="testResults"></div>
	
	<input type="submit" value="Submit"/>
</form>
<br>
	              <input type="button" name="test" value="Test"  onClick="
document.forms['addspider'].elements['url'].value=document.forms['addspider'].elements['url'].value.replace('+', '%2B');
//document.forms['addspider'].elements['url'].value=document.forms['addspider'].elements['url'].value.replace('/', '%2F'); 
postContent('testQuickQuoteEntry.php', 
'url='+escape(document.forms['addspider'].elements['url'].value)
+'&companycfg='+escape(document.forms['addspider'].elements['companies'].value)
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