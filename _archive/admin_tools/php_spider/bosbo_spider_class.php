<?php
class Spider_data
{
	var $orderid;
	var $url;
	var $validrobot;
	var $active;
	var $preprice;
	var $postprice;
	var $prequantity;
	var $postquantity;
	var $last_spidered;
	var $prepostage;
	var $postpostage;
	
	function Spider_data($orderid='', $url='', $validrobot='', $active='', $preprice='', $postprice='', $prequantity='', $postquantity='', $last_spidered='', $prepostage='', $postpostage='')
	{
		$this->orderid = $orderid;
		$this->url = $url;
		$this->validrobot = $validrobot;
		$this->active = $active;
		$this->preprice = $preprice;
		$this->postprice = $postprice;
		$this->prequantity = $prequantity;
		$this->postquantity = $postquantity;
		$this->last_spidered = $last_spidered;
		$this->prepostage = $prepostage;
		$this->postpostage = $postpostage;
	}
	
	function Get($orderId)
	{
		$Database = new dbConnection();
		$this->pog_query = "select * from `spider_data` where `orderid`='".intval($orderId)."' LIMIT 1";
		$Database->Query($this->pog_query);
		$this->orderid = $Database->unescape($Database->Result(0, "orderid"));
		$this->url = $Database->unescape($Database->Result(0, "url"));
		$this->validrobot = $Database->unescape($Database->Result(0, "validrobot"));
		$this->active = $Database->unescape($Database->Result(0, "active"));
		$this->preprice = $Database->unescape($Database->Result(0, "preprice"));
		$this->postprice = $Database->unescape($Database->Result(0, "postprice"));
		$this->prequantity = $Database->unescape($Database->Result(0, "prequantity"));
		$this->postquantity = $Database->unescape($Database->Result(0, "postquantity"));
		$this->last_spidered = $Database->unescape($Database->Result(0, "last_spidered"));
		$this->prepostage = $Database->unescape($Database->Result(0, "prepostage"));
		$this->postpostage = $Database->unescape($Database->Result(0, "postpostage"));
		return $this;
	}
	
	function Save()
	{
		$Database = new dbConnection();
		$this->pog_query = "select orderid from `spider_data` where `orderid`='".$this->orderid."' LIMIT 1";
		$Database->Query($this->pog_query);
		if ($Database->Rows() > 0)
		{
			$this->pog_query = "update `spider_data` set 
			`url`='".$Database->escape($this->url)."',
			`validrobot`='".$Database->escape($this->validrobot)."',
			`active`='".$Database->escape($this->active)."',
			`preprice`='".$Database->escape($this->preprice)."',
			`postprice`='".$Database->escape($this->postprice)."',
			`prequantity`='".$Database->escape($this->prequantity)."',
			`postquantity`='".$Database->escape($this->postquantity)."',
			`last_spidered`='".$Database->escape($this->last_spidered)."',
			`prepostage`='".$Database->escape($this->prepostage)."',
			`postpostage`='".$Database->escape($this->postpostage)."' where `orderid`='".$Database->escape($this->orderid)."'";
		}
		else
		{
			 $this->pog_query= "insert into `spider_data` (`orderid`, `url`, `validrobot`, `active`, `preprice`, `postprice`, `prequantity`, `postquantity`, `last_spidered`, `prepostage`, `postpostage`) values (
			'".$Database->escape($this->orderid)."', 
			'".$Database->escape($this->url)."', 
			'".$Database->escape($this->validrobot)."', 
			'".$Database->escape($this->active)."', 
			'".$Database->escape($this->preprice)."', 
			'".$Database->escape($this->postprice)."', 
			'".$Database->escape($this->prequantity)."', 
			'".$Database->escape($this->postquantity)."',
			'".$Database->escape($this->last_spidered)."',
			'".$Database->escape($this->prepostage)."', 
			'".$Database->escape($this->postpostage)."'
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
		$this->pog_query = "delete from `order` where `orderid`='".$Database->escape($this->orderid)."'";
		return $Database->Query($this->pog_query);
	}
	
	function get_active_validated_links($limit=9999999) {
		$Database = new dbConnection();
		//$this->pog_query = "SELECT * FROM `spider_data` WHERE `validrobot` = '1' AND `active` = '1' ORDER BY `last_spidered` ASC LIMIT " . $limit;
		$this->pog_query = "SELECT * FROM `spider_data`, `order` WHERE order.orderid = spider_data.orderid AND spider_data.validrobot = '1' AND spider_data.active = '1' ORDER BY spider_data.last_spidered ASC limit " . $limit;
		$Database->Query($this->pog_query);
		$myArray = Array();
		for ($i=0; $i < $Database->Rows(); $i++)
		{
			array_push($myArray, $Database->unescape($Database->Result($i, "orderid")));
		}
		return $myArray;
	}
	
	function getPrice()	{		return $this->price;	}
	
	function setLast_spidered($a) {
		$this->last_spidered = $a;
	}
	function setPrequantity($a) {
		$this->prequantity= $a;
	}
	function setPostquantity($a) {
		$this->postquantity = $a;
	}
}
?>