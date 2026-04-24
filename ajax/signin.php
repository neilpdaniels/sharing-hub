<?php 
  if(file_exists("ajax_include_all.php")){
    include "ajax_include_all.php";
  }

$myFile = "../log/signin.log";
$fh = fopen($myFile, 'a') or die("can't open file");
$stringData = $_POST['username']." logged in at ".date(DATE_RFC822)."\n";
fwrite($fh, $stringData);
fclose($fh);
$signin_user = new user($_POST['username'], $_POST['password']);
$signin_user->loadUserDetails();
if($signin_user->authUser()){
  echo "authorised";
}
?>