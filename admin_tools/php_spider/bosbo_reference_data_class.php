<?php
class Reference_data
{
    	var $reference_data_id;
	var $reference_data_type;
	var $url;
	var $validrobot;
	var $active;
	var $pre_target_data;
	var $post_target_data;
	var $reference_data_value;
	var $last_spidered;
	
	function Reference_data($reference_data_id='', $reference_data_type='', $url='', $validrobot='', $active='', $pre_target_data='', $post_target_data='', $reference_data_value='', $last_spidered='')
	{
            	$this->reference_data_id =  $reference_data_id;
		$this->reference_data_type = $reference_data_type;
		$this->url = $url;
		$this->validrobot = $validrobot;
		$this->active = $active;
		$this->pre_target_data = $pre_target_data;
		$this->post_target_data = $post_target_data;
		$this->reference_data_value = $reference_data_value;
		$this->last_spidered = $last_spidered;
	}
	
	function Get($refId)
	{
		$Database = new dbConnection();
		$this->pog_query = "select * from `reference_data` where `reference_data_id`='".intval($refId)."' LIMIT 1";
		$Database->Query($this->pog_query);
                $this->reference_data_id = $Database->unescape($Database->Result(0, "reference_data_id"));
		$this->reference_data_type = $Database->unescape($Database->Result(0, "reference_data_type"));
		$this->url = $Database->unescape($Database->Result(0, "url"));
		$this->validrobot = $Database->unescape($Database->Result(0, "validrobot"));
		$this->active = $Database->unescape($Database->Result(0, "active"));
		$this->pre_target_data = $Database->unescape($Database->Result(0, "pre_target_data"));
		$this->post_target_data = $Database->unescape($Database->Result(0, "post_target_data"));
		$this->reference_data_value = $Database->unescape($Database->Result(0, "reference_data_value"));
		$this->last_spidered = $Database->unescape($Database->Result(0, "last_spidered"));
		return $this;
	}
	
	function Save()
	{
		$Database = new dbConnection();
		$this->pog_query = "select reference_data_type from `reference_data` where `reference_data_id`='".$this->reference_data_id."' LIMIT 1";
		$Database->Query($this->pog_query);
		if ($Database->Rows() > 0)
		{
			$this->pog_query = "update `reference_data` set 
			`reference_data_type`='".$Database->escape($this->reference_data_type)."',
			`url`='".$Database->escape($this->url)."',
			`validrobot`='".$Database->escape($this->validrobot)."',
			`active`='".$Database->escape($this->active)."',
			`pre_target_data`='".$Database->escape($this->pre_target_data)."',
			`post_target_data`='".$Database->escape($this->post_target_data)."',
			`reference_data_value`='".$Database->escape($this->reference_data_value)."',
			`last_spidered`='".$Database->escape($this->last_spidered)."'
			 where `reference_data_type`='".$Database->escape($this->reference_data_type)."'";
                }
		else
		{
			 $this->pog_query= "insert into `reference_data` (`reference_data_id`, `reference_data_type`, `url`, `validrobot`, `active`, `pre_target_data`, `post_target_data`, `reference_data_value`, `last_spidered`) values (
			'".$Database->escape($this->reference_data_id)."', 
			'".$Database->escape($this->reference_data_type)."', 
			'".$Database->escape($this->url)."', 
			'".$Database->escape($this->validrobot)."', 
			'".$Database->escape($this->active)."', 
			'".$Database->escape($this->pre_target_data)."', 
			'".$Database->escape($this->post_target_data)."', 
			'".$Database->escape($this->reference_data_value)."', 
			'".$Database->escape($this->last_spidered)."',
			 )";
		}
		$Database->InsertOrUpdate($this->pog_query);
		if ($this->orderId == "")
		{
			$this->orderId = $Database->GetCurrentId();
		}
		return $this->orderId;
	}
	
	function Delete()
	{
		$Database = new dbConnection();
		$this->pog_query = "delete from `order` where `reference_data_type`='".$Database->escape($this->reference_data_type)."'";
		return $Database->Query($this->pog_query);
	}
	
	function get_active_validated_links($limit=9999999) {
		$Database = new dbConnection();
		$this->pog_query = "SELECT * FROM `reference_data` WHERE `validrobot` = '1' AND `active` = '1' ORDER BY `last_spidered` ASC LIMIT " . $limit;
		//$this->pog_query = "SELECT * FROM `reference_data`, `order` WHERE order.reference_data_type = reference_data.reference_data_type AND reference_data.validrobot = '1' AND reference_data.active = '1' ORDER BY reference_data.last_spidered ASC limit " . $limit;
		$Database->Query($this->pog_query);
		$myArray = Array();
		for ($i=0; $i < $Database->Rows(); $i++)
		{
			array_push($myArray, $Database->unescape($Database->Result($i, "reference_data_id")));
		}
		return $myArray;
	}
	

        
	function setLast_spidered($a) {
		$this->last_spidered = $a;
	}
        
        function setReferenceDataValue($a) {
            $this->reference_data_value = $a;
        }
}
?>