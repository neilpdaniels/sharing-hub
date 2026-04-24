<?php
if(file_exists("../../include/php_library_fns/xml_functions.php")){	include "../../include/php_library_fns/xml_functions.php";}
if(file_exists("../../include/php_library_fns/db_functions.php")){	include "../../include/php_library_fns/db_functions.php";}
if(file_exists("../../include/php_library_fns/mkThumb.php")){	include "../../include/php_library_fns/mkThumb.php";}

if (!isset($_SESSION)){
	session_name('bosbo-session');
	session_start();
}
	
$to_continue = false;
$upload_error = "";

// needed if exif is not configured in php install;
$imtype = -1;
if ($_FILES['userfile']['type'] == 'image/gif') {
	$imtype = 1;
}
elseif ($_FILES['userfile']['type'] == 'image/jpg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/jpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/pjpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/png') {
	$imtype = 3;
}

if (isset($_SESSION['valid_user'])){

if($_POST["action"] == "Upload Image")
{
	
	
	

// needed if exif is not configured in php install;
$imtype = -1;
if ($_FILES['userfile']['type'] == 'image/gif') {
	$imtype = 1;
}
elseif ($_FILES['userfile']['type'] == 'image/jpg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/jpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/pjpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/png') {
	$imtype = 3;
}
	?>
	
	<html>
<head>
  <title>Add Offer - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../../css/L2_style.css"/>
</head>
<body>
	<?php
  if ($_FILES['userfile']['error'] > 0)
  {
    switch ($_FILES['userfile']['error'])
    {
      //upload_max_filesize
      case 1:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file exceeds maximum size allowed</font></b></div>';  break;
      //max_file_size
      case 2:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file exceeds maximum size allowed</font></b></div>';  break;
      case 3:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: file only partially uploaded - please retry</font></b></div>';  break;
      case 4:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: no file selected - please select file</font></b></div>';  break;
    }
    $to_continue = true;
  } else {

  // Does the file have the right MIME type? pjpeg??
  if (!(($_FILES['userfile']['type'] == 'image/jpeg') || ($_FILES['userfile']['type'] == 'image/pjpeg') || ($_FILES['userfile']['type'] == 'image/jpg') || ($_FILES['userfile']['type'] == 'image/gif') || ($_FILES['userfile']['type'] == 'image/png')))
  {
  	$upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file is not of the correct format</font></b></div>';
  	$to_continue = true;
  } else {

  	
  	
  	
  	
  	// remove any other files that have the same name - different extension - stops confusion later
  	if (($_FILES['userfile']['type'] != 'image/jpeg')) {
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpeg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpeg");
		}
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpeg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpeg");
		}
  	}
  	if (($_FILES['userfile']['type'] != 'image/pjpeg')) {
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpeg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpeg");
		}
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpeg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpeg");
		}
  	}
  	if ($_FILES['userfile']['type'] != 'image/jpg') {
  		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.jpg");
		}
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpg")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".jpg");
		}
  	} 
  	if ($_FILES['userfile']['type'] != 'image/gif') {
  		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.gif")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.gif");
		}
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".gif")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".gif");
		}
  	}
  	if ($_FILES['userfile']['type'] != 'image/png') {
  		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.png")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id']."_thumb.png");
		}
		if (file_exists("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".png")) {
  					unlink("../../images/user_images/temp_addOffer/".$_GET['temp_order_id'].".png");
		}
  	}

  // to get the file extension reverse the string and get the first element
  $nameArray = explode('.', strrev($_FILES['userfile']['name']));
  $file_extension =strtolower(strrev($nameArray[0]));
  
  $upfile = '../../images/user_images/temp_addOffer/originals/'.$_POST["temp_order_id"].".".$file_extension;//original - to be deleted
  $upfile_large = '../../images/user_images/temp_addOffer/'.$_POST["temp_order_id"].".".$file_extension;//to be large
  $upfile_thumb = '../../images/user_images/temp_addOffer/'.$_POST["temp_order_id"]."_thumb.".$file_extension;//to be thumbnail

  if (is_uploaded_file($_FILES['userfile']['tmp_name'])) 
  {
     if (!move_uploaded_file($_FILES['userfile']['tmp_name'], $upfile))
     {
        echo 'Problem: Could not move file to destination directory.  Please contact Bosbo support.';
        exit;
     } else {
     	
     	// this is where we need to modify the picture attributes - for the moment the thumbnail is just the other copied.s
     	//copy($upfile, $upfile_thumb);
     	
     	//if (mkthumb($upfile, $upfile_large, 400) &&	mkthumb($upfile, $upfile_thumb, 102)) {
	    if (mkthumb($upfile, $upfile_large, $imtype, 400) &&	mkthumb($upfile, $upfile_thumb, $imtype, 102)) {	
	     	unlink('../../images/user_images/temp_addOffer/originals/'.$_POST["temp_order_id"].".".$file_extension);
     		echo '<div id="bosbo_logo_small" align="center"><img src="../../images/bosbo_logo_small.gif"></div><br><br>';
     		echo '<div id="small">File uploaded successfully</div><br><br><br>';
     		echo '<div align="center" class="bbsmall"><a href="javascript:window.close();" align="center">close this window</a></div>';
     	} else {
     		// error modifing images - the error will already have been displayed.
     		exit;
     	}	
     }
  } 
  else 
  {
    echo 'Problem: Possible file upload attack. Filename: ';
    echo $_FILES['userfile']['name'];
    echo '.<br>Please contact Bosbo support.';
    exit;
  }
  }
  }
}
  

// need to put in another clause or 
if($_POST["action"] != "Upload Image" || $to_continue==true) {
	if (isset($_GET['temp_order_id']) || isset($_POST["temp_order_id"])) {  	

  	?>

<html>
<head>
  <title>Add Offer - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../../css/L2_style.css"/>
</head>
<body>

  <div id="bosbo_logo_small" align="center"><img src="../../images/bosbo_logo_small.gif"></div><br>
  <?php
  if ($upload_error!="") { echo $upload_error; }
  ?>
  <form enctype="multipart/form-data" method="POST" action="<?php echo $_SERVER['PHP_SELF']."?temp_order_id=".$_GET['temp_order_id'];?>">
    <div id="xsmall">
      Please select the image you wish to be associated with your offer.  The image must have a format of either jpeg, gif or png, and must be under 500 kilobytes (approx. 0.5mb) in size.
    </div><br>
    <input type="hidden" name="MAX_FILE_SIZE" value="500000">
    <input name="userfile" type="file" size="50">
    <input type="hidden" name="temp_order_id" value="<?php echo $_GET['temp_order_id']; ?>"
    <br><br>
    <div align="center"><input type="submit" value="Upload Image" name="action"></div>
  </form>
</body>
</html>
<?php
} else {
?>
<html>
<head>
  <title>Add Offer - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../../css/L2_style.css"/>
</head>
<body>
  <div id="bosbo_logo_small" align="center"><img src="../../images/bosbo_logo_small.gif"></div>
    <div id="xsmall">
      ERROR - please contact Bosbo support
    </div>
</body>
</html>
<?php
}
}
}
?>