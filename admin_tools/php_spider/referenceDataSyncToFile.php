<?php
if (getenv("ISCRON")==1) {
    include "/home/bosbodev/public_html/include/php_library_fns/db_functions.php";
    include "/home/bosbodev/public_html/include/php_library_fns/xml_functions.php";
    include "/home/bosbodev/public_html/include/objects/bosbo_order_class.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/CURL.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/bosbo_reference_data_class.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/simple_html_dom.php";
} else {
    if(file_exists("CURL.php")){	    include "CURL.php"; }
    if(file_exists("bosbo_reference_data_class.php")) {  include "bosbo_reference_data_class.php";  }
    if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
    if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
    if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
}

/**
 * Find the position of the Xth occurrence of a substring in a string
 * @param $haystack
 * @param $needle
 * @param $number integer > 0
 * @return int
 */
function strposX($haystack, $needle, $number){
    if($number == '1'){
        return strpos($haystack, $needle);
    }elseif($number > '1'){
        return strpos($haystack, $needle, strposX($haystack, $needle, $number - 1) + strlen($needle));
    }else{
        return error_log('Error: Value for parameter $number is out of range');
    }
}

/*if (isset($_GET['login'])&&isset($_GET['password'])) {
	$user1 = new User($_GET['login'],'','','','','','','','',$_GET['password'],'','', '');
	if($user1->AuthUser()){
		$user1 = $user1->GetByUsername($_GET['login']);
		$id = $user1->getUserId();
		if ($id<0) {
*/
$ref_data_all = new Reference_data();
if (isset($_GET['limit'])) {
	$to_ref_data = $ref_data_all->get_active_validated_links($_GET['limit']);
} else {
	$to_ref_data = $ref_data_all->get_active_validated_links();
}
shuffle($to_ref_data);
$to_report = array();
$number_to_ref_data = 0;

$myFile = "refDataResults.html";
$fh = fopen($myFile, 'w') or die("can't open file");

$refData = "";
$i = 0;
echo sizeof($to_ref_data);
foreach ($to_ref_data as $value)
{
    $i++;
    //if ($i<10) {
    $refData = "";
	
    // for each validated URL
    $this_ref_data = new Reference_data();
    $this_ref_data->Get($value);

    $url = new CURL();

    $this_ref_data->setLast_spidered(time());
    $this_ref_data->Save();
	
    $pre_target_data = preg_replace ('/\s/', '', $this_ref_data->pre_target_data);
    $post_target_data = preg_replace ('/\s/', '', $this_ref_data->post_target_data);
	
    //$toWriteData .=  "<td width='20%'>Item:". $orderRecord->getorderId()."</td>";
    $data = preg_replace ('/\s/', '', $url->get($this_ref_data->url));
	
    if ($data!='') {
        //echo $data;
        if (trim($pre_target_data)!=''&&trim($post_target_data)!='') {
            //$price = substr($data, (strpos($data, $pre_target_data)+strlen($pre_target_data)), -1);
            $price = substr($data, (strposX($data, $pre_target_data, 1)+strlen($pre_target_data)), -1);
            //echo $price;
            //$price = substr($data, ( preg_match($pre_target_data, $data)+strlen($pre_target_data)), -1);
            $price = substr($price, 0, strposX($price, $post_target_data, 1));
            $price = str_replace(",", "", $price);
            $toWriteData .= '<p>'+$this_ref_data->reference_data_value +' 000000 '+$price+'</p>';
            if (strlen($price)<=255) {
                echo "\n".date("Y-m-d h:i:sa")." : ". $this_ref_data->url . " - " +$price;
                $this_ref_data->setReferenceDataValue($price);
                $this_ref_data->Save();
            }
        }
    }
}
fwrite($fh, $toWriteData);
fclose($fh);                
?>