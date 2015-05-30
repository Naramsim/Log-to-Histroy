<html>
<!--
In this webpage is presented a tree graph which first level nodes represents every IP who has been in a specific website.
we can understand who visited a specific website by parsing the access.log made by the webserver(apache2, nginx, ...) of that specific website
For parsing the log PHP invokes a script made in Python that creates a file that will be interpreted by some Javascript code.
The children of a first-level node are the pages that a user has visited coming directly or from another site(by clicking a link), the children of these nodes are the pages visited coming from parent(by clicking a link), and so on

In this case the script is called "main.py", and the Javascript code is in "tree_graph.js"
-->
<head>
	<link href="css/header.css" rel="stylesheet" >
    <link href="https://mtgfiddle.me/tirocinio/pezze/css/bootstrap-datetimepicker.min.css" rel="stylesheet" > <!-- Datetime Picker plugin css (for calendar) -->
    <link href="https://mtgfiddle.me/tirocinio/pezze/css/bootstrap_.css" rel="stylesheet" > <!-- Bootstrap custom css -->
    <script src="https://code.jquery.com/jquery-1.11.2.min.js" type="text/javascript"></script><!-- jQuery -->
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.5/d3.min.js"></script><!-- D3 -->
    <script src="https://netdna.bootstrapcdn.com/twitter-bootstrap/2.2.2/js/bootstrap.min.js" type="text/javascript"></script><!-- Bootstrap -->
    <script src="https://mtgfiddle.me/tirocinio/pezze/bootstrap-datetimepicker.min.js" type="text/javascript"></script><!-- Datetime Picker plugin (for calendar) -->

	<title>Log to History</title>
	<link href='https://fonts.googleapis.com/css?family=Open+Sans:400' rel='stylesheet' type='text/css'> <!-- Font Google Open Sans -->
	<link href='css/tree.css' rel='stylesheet' type='text/css'>
	<script src="https://mtgfiddle.me/tirocinio/pezze/d3tip.js" type="text/javascript"></script> <!-- Bootstrap -->
	<script src="js/tree_graph.js" type="text/javascript"></script>
</head>

<?php 
	if( isset($_POST['start_date']) && isset($_POST['end_date']) ){
		//print $_POST['start_date']." ".$_POST['end_date'];
		$command = "./main.py ".$_POST['start_date']." ".$_POST['end_date']." 0";	
		print $command;
		ob_start();
		system($command, $status);
		$output1 = json_decode( ob_get_clean() , true);
		$json_string = json_encode($output1, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
		die();
	}
?>

<body>
	<div id="header">
        <div id="search"></div>
        <div id="graphic-title-and-subtitle">
            <div id="graphic-title">Accurated user history on a site</div>
            <div id="graphic-subtitle">Choose the time to analyze</div>
            
			  <div id="datetimepickerStart" class="input-append date">
			    <input data-format="dd/MM/yyyy@hh:mm:ss" type="text" id="start_date" placeholder="start"></input>
			    <span class="add-on">
			      <i data-time-icon="icon-time" data-date-icon="icon-calendar">
			      </i>
			    </span>
			  </div>
			  <div id="datetimepickerEnd" class="input-append date">
			    <input data-format="dd/MM/yyyy@hh:mm:ss" type="text" id="end_date" placeholder="end"></input>
			    <span class="add-on">
			      <i data-time-icon="icon-time" data-date-icon="icon-calendar">
			      </i>
			    </span>
			  </div>
			
			<script type="text/javascript">
			  $(function() {
			    $('#datetimepickerStart, #datetimepickerEnd').datetimepicker({
			    	format: 'dd/MM/yyyy@hh:mm:ss'
			    	//language: 'pt-BR'
			    });
			  });
			</script>
			<button id="submit" type="button" class="btn btn-default btn-sm">Send</button>
			<script type="text/javascript">
		        $('#submit').on("click",function() { 
		        	var date_regex = /^([123]0|[012][1-9]|31)\/(0[1-9]|1[012])\/(19[0-9]{2}|2[0-9]{3})@([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])$/ ;
					var to_submit_s = $("#start_date").val();
					var to_submit_e = $("#end_date").val();
		        	if( (date_regex.test(to_submit_s)) && (date_regex.test(to_submit_e)) ){
		        		$.ajax({
							url: 'tree.php',
							type: 'POST',
							data: { 'start_date': to_submit_s,
									'end_date': to_submit_e}, // An object with the key 'submit' and value 'true;
							success: function (data) {
								  prepare_graph();
								}
						});
		        	}	
	        	});
	        </script>
        </div>
    </div>
    <div id="graph" style="position:absolute;top:90px;width:100%;height:80%;"></div>
</body>

<html>