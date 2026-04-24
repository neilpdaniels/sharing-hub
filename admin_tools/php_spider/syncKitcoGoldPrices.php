<?php
if (getenv("ISCRON")==1) {
    include "/home/bosbodev/public_html/include/php_library_fns/db_functions.php";
    include "/home/bosbodev/public_html/include/php_library_fns/xml_functions.php";
    include "/home/bosbodev/public_html/include/objects/bosbo_order_class.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/CURL.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/bosbo_reference_data_class.php";
    include "/home/bosbodev/public_html/admin_tools/php_spider/simple_html_dom.php";
} else {
    if(file_exists("./CURL.php")){	    include "./CURL.php"; }
    if(file_exists("./bosbo_reference_data_class.php")) {  include "./bosbo_reference_data_class.php";  }
    if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
    if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
    if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
    if(file_exists("./simple_html_dom.php")) { include('./simple_html_dom.php'); }
}
//$html = new simple_html_dom();

// bid is value 5
$this_ref_data = new Reference_data();
$this_ref_data->Get(5);
$this_ref_data->setLast_spidered(time());
//echo $this_ref_data->url;
 /*
$doc = new DOMDocument();
$doc->loadHTMLFile($this_ref_data->url);
foreach ($doc->getElementsByTagName('td') as $td) {
    $children = $td->childNodes;
    foreach ($children as $child) 
    { 
        echo $child->saveHTML();
    }
}
*/
$html = file_get_html($this_ref_data->url);
//echo get_class($html);
echo implode(" ",get_class_methods($html));
//if (method_exists($html,"find")) {
     // then check if the html element exists to avoid trying to parse non-html
//     if ($html->find('html')) {
          // and only then start searching (and manipulating) the dom 
        $element = $html->find("table");
        $element2 = $element[2]->find("tr");
        $element3 = $element2[2]->find("td");
        $element4 = $element3[0]->find("font");
        if (is_numeric($element4[0]->innertext)) {
            $this_ref_data->setReferenceDataValue($element4[0]->innertext);
            $this_ref_data->Save();
            echo "\n".date("Y-m-d h:i:sa")." updating bid to: ".$element4[0]->innertext;
        }
        // offer is ref id 6
        $this_ref_data->Get(6);
        $this_ref_data->setLast_spidered(time());
        $element4 = $element3[1]->find("font");
        if (is_numeric($element4[0]->innertext)) {
            $this_ref_data->setReferenceDataValue($element4[0]->innertext);
            $this_ref_data->Save();
            echo "\n".date("Y-m-d h:i:sa")." updating offer to: ".$element4[0]->innertext;
        }
 //   }
//}

//echo $html->childNodes(0)->childNodes(1);
?>