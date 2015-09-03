<html>
<head>
<title>HYDRO CHECKER</title>
<link rel = "stylesheet" type = "text/css" href = "style.css">
<link rel = "stylesheet" type = "text/css" href = "stylesProteins.css">
<link rel = "stylesheet" type = "text/css" href = "theme.css">
<link rel = "stylesheet" type = "text/css" href = "reset.css">
<link href='http://fonts.googleapis.com/css?family=Raleway:400' rel='stylesheet' type='text/css'>
<script src="jquery-1.11.3.min.js"></script>
<script src="jquery.validate.min.js"></script>
<script src="shine.min.js"></script>
<script src="pace.min.js"></script>
<script type='text/javascript' src='pv/js/pv.min.js'></script>

<script>
$(document).ready(function () {

    $('#myform').validate({ // initialize the plugin
        rules: {
            BactForm: {
                selectcheck: true
            },
            NumForm: {
                selectcheckNum: true
            },
            submitHandler: function (form) { // for demo
            alert('valid form submitted'); // for demo
            return false; // for demo
        }
        }
    });

    jQuery.validator.addMethod('selectcheck', function (value) {
        if (value != ''){$('#Chooser').html('<p id = "Chooser">Select a Bacteria from NCBI</p>');return true;}
        else{$('#Chooser').html('<p id = "Chooser" style="color:#FF6666">BACTERIA REQUIRED</p>');return false;}
    },"");
    jQuery.validator.addMethod('selectcheckNum', function (value) {
        if (value != ''){$('#Chooser1').html('<p id = "Chooser1">Select # of Proteins to graph</p>');return true;}
        else{$('#Chooser1').html('<p id = "Chooser1" style="color:#FF6666">NUMBER REQUIRED</p>');return false;}
    },"");

});
</script>
</head>

<body>

<?php


exec("perl parser.pl", $output);

echo "</br>";
echo "</br>";
echo "</br>";
echo "<div align='center'>";
echo "<form id='myform' action='#' method='post'>";
echo "<a id = 'Title' href='index.php'>Hydrophobic % Finder</a>";
echo "</br>";
echo "</br>";
?>
<script>
// all parameters are optional and can be changed later
 var config = new shinejs.Config({
      numSteps: 12,
      opacity: .15,
      shadowRGB: new shinejs.Color(0, 0, 0)
    });

var shine = new Shine(document.getElementById('Title'),config);
window.addEventListener('mousemove', function(event) {
  shine.light.position.x = event.clientX;
  shine.light.position.y = event.clientY;
  shine.draw();
}, false);
</script>
<?php
#echo "<p id = 'TitleSub'>Scott Ouellette Comp 601</p>";
echo "</br>";echo "</br>";
echo "<p id = 'Chooser'>Select a Bacteria from NCBI</p>";
echo "</br>";
echo "<span class='custom-dropdown custom-dropdown--emerald'>";
echo "<select class='custom-dropdown__select custom-dropdown__select--emerald' name='BactForm'>";
echo "<option value=''>Select...</option>";
foreach ($output as $value)
	echo "<option value=$value>$value</option>";
echo "</select>";
echo "</span>";
echo "</br>";
echo "</br>";
echo "<p id = 'Chooser1'>Select # of Proteins to graph</p>";
echo "</br>";
echo "<span class='custom-dropdown custom-dropdown--emerald'>";
echo "<select class='custom-dropdown__select custom-dropdown__select--emerald' name='NumForm'>";
echo "<option value=''>Select...</option>";
$x = 10;
while( $x <= 25){
  echo "<option value=$x>$x</option>";
  $x++;
}
echo "</select>";
echo "</span>";
echo "</br>";echo "</br>";echo "</br>";
echo "<input id='Submit' type='submit' name='submit' value='Submit' />";
echo "</form>";
echo "</div>";
echo "</br>";

if(isset($_POST['submit'])){
$select = $_POST['BactForm'];
$num = $_POST['NumForm'];
echo "<div align = 'center'><p id='Message'>You have selected > " . $select . "</p></div>";
echo "</br>";

$cmd = "python wget_dl.py " . $select;
exec($cmd,$outputa);
foreach ($outputa as $valuea)
	echo $valuea;

#$cmda = "python test.py " . $select . " " . $num . " 2>&1";
$cmda = "python test.py " . $select . " " . $num;
exec($cmda,$outputb);
foreach ($outputb as $valueb)
	echo $valueb;

$f1 = file_get_contents("DNA",FILE_USE_INCLUDE_PATH);
$f2 = file_get_contents("BACID",FILE_USE_INCLUDE_PATH);
$f3 = file_get_contents("RANGES",FILE_USE_INCLUDE_PATH);
$f4 = file_get_contents("PLUSMINUS",FILE_USE_INCLUDE_PATH);
$f5 = file_get_contents("LENGTHS",FILE_USE_INCLUDE_PATH);
$f6 = file_get_contents("GENES",FILE_USE_INCLUDE_PATH);
$f7 = file_get_contents("MINUSSTRANDS",FILE_USE_INCLUDE_PATH);
$f8 = file_get_contents("PROTEINS",FILE_USE_INCLUDE_PATH);
$f9 = file_get_contents("HASH",FILE_USE_INCLUDE_PATH);

echo("<div align = 'center'><p id = 'Message'>$f2</p></div>");
echo "<br>";
?>

<div class = 'container'>


<?php

echo "<div class = 'REKT'><input id='clicky' type='submit' class = 'Button' value='Show DNA Sequence'></input></div>";
?>
<script>
var clicks = 0
$('#clicky').click(function() {
$('.DNA').toggleClass('hide_this');
if(clicks % 2 == 0){
$('#clicky').val('Hide DNA Sequence');
}
else{
$('#clicky').val('Show DNA Sequence');
}
clicks++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky1' type='submit' class = 'Button' value='Show Ptt Ranges'></input></div>";
?>
<script>
var clicks1 = 0
$('#clicky1').click(function() {
$('.Ranges').toggleClass('hide_this');
if(clicks1 % 2 == 0){
$('#clicky1').val('Hide Ptt Ranges');
}
else{
$('#clicky1').val('Show Ptt Ranges');
}
clicks1++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky2' type='submit' class = 'Button' value='Show +/-'></input></div>";
?>
<script>
var clicks2 = 0
$('#clicky2').click(function() {
$('.PLUSMINUS').toggleClass('hide_this');
if(clicks2 % 2 == 0){
$('#clicky2').val('Hide +/-');
}
else{
$('#clicky2').val('Show +/-');
}
clicks2++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky3' type='submit' class = 'Button' value='Show Gene Lengths'></input></div>";
?>
<script>
var clicks3 = 0
$('#clicky3').click(function() {
$('.Lengths').toggleClass('hide_this');
if(clicks3 % 2 == 0){
$('#clicky3').val('Hide Gene Lengths');
}
else{
$('#clicky3').val('Show Gene Lengths');
}
clicks3++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky4' type='submit' class = 'Button' value='Show Genes'></input></div>";
?>
<script>
var clicks4 = 0
$('#clicky4').click(function() {
$('.Genes').toggleClass('hide_this');
if(clicks4 % 2 == 0){
$('#clicky4').val('Hide Genes');
}
else{
$('#clicky4').val('Show Genes');
}
clicks4++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky5' type='submit' class = 'Button' value='Show Minus Strands'></input></div>";
?>
<script>
var clicks5 = 0
$('#clicky5').click(function() {
$('.MINUSSTRANDS').toggleClass('hide_this');
if(clicks5 % 2 == 0){
$('#clicky5').val('Hide Minus Strands');
}
else{
$('#clicky5').val('Show Minus Strands');
}
clicks5++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky6' type='submit' class = 'Button' value='Show Proteins'></input></div>";
?>
<script>
var clicks6 = 0
$('#clicky6').click(function() {
$('.PROTEINS').toggleClass('hide_this');
if(clicks6 % 2 == 0){
$('#clicky6').val('Hide Proteins');
}
else{
$('#clicky6').val('Show Proteins');
}
clicks6++;
})
</script>
<?php

echo "<div class = 'REKT'><input id='clicky7' type='submit' class = 'Button' value='Show Sorted Hash'></input></div>";
?>
<script>
var clicks7 = 0
$('#clicky7').click(function() {
$('.HASH').toggleClass('hide_this');
if(clicks7 % 2 == 0){
$('#clicky7').val('Hide Sorted Hash');
}
else{
$('#clicky7').val('Show Sorted Hash');
}
clicks7++;
})
</script>
<?php

echo "<br>";
echo "<br>";
echo "<div >";
echo "<a href='https://plot.ly/~scottx611x1c74/10/' target='_blank' title='Top Hydrophobic Proteins ' . $select . ' style='display: block; text-align: center;'><img src='https://plot.ly/~scottx611x1c74/10.png' alt='Top Hydrophobic Proteins  ' . $select . ' style='max-width: 85%;'  onerror='this.onerror=null;this.src='https://plot.ly/404.png';' /><br><br></a><script data-plotly='scottx611x1c74:10' src='https://plot.ly/embed.js' async></script>";
echo "</div>";
echo "<br>";




}

?>
</div>

<br>
<br>
<script type='text/javascript'>
// override the default options with something less restrictive.
var options = {
  width: 600,
  height: 600,
  antialias: true,
  quality : 'medium'
};
// insert the viewer under the Dom element with id 'gl'.
var viewer = pv.Viewer(document.getElementById('viewer'), options);
</script>
<script type='text/javascript'>

function loadMethylTransferase() {
  // asynchronously load the PDB file for the dengue methyl transferase
  // from the server and display it in the viewer.
  pv.io.fetchPdb('1r6a.pdb', function(structure) {
      // display the protein as cartoon, coloring the secondary structure
      // elements in a rainbow gradient.
      viewer.cartoon('protein', structure, { color : color.ssSuccession() });
      // there are two ligands in the structure, the co-factor S-adenosyl
      // homocysteine and the inhibitor ribavirin-5' triphosphate. They have
      // the three-letter codes SAH and RVP, respectively. Let's display them
      // with balls and sticks.
      var ligands = structure.select({ rnames : ['SAH', 'RVP'] });
      viewer.ballsAndSticks('ligands', ligands);
      viewer.centerOn(structure);
  });
}

// load the methyl transferase once the DOM has finished loading. That's
// the earliest point the WebGL context is available.
document.addEventListener('DOMContentLoaded', loadMethylTransferase);
</script>
<br>
<br>

<?php
echo("<div class='DNA hide_this' align = 'center'><br>$f1<br></div>");
echo("<div class='Ranges hide_this' align = 'center'><br>$f3<br></div>");
echo("<div class='PLUSMINUS hide_this' align = 'center'><br>$f4<br></div>");
echo("<div class='Lengths hide_this' align = 'center'><br>$f5<br></div>");
echo("<div class='Genes hide_this' align = 'center'><br>$f6<br></div>");
echo("<div class='MINUSSTRANDS hide_this' align = 'center'><br>$f7<br></div>");
echo("<div class='PROTEINS hide_this' align = 'center'><br>$f8<br></div>");
echo("<div class='HASH hide_this' align = 'center'><br>$f9<br></div>");
?>
<a href="#0" class="cd-top">Top</a>
<script src="main.js"></script>
<script src="modernizr.js"></script>
</body>
<div align="center">
<footer style="color:white;font-family: Raleway;">Scott Ouellette ©2015 all rights reserved <a href = "index.html" style="color:white;"> www.scott-ouellette.com</a></footer>
</div>
</html>

<?php

function deleteDirectory($dir) {
    if (!file_exists($dir)) {
        return true;
    }

    if (!is_dir($dir)) {
        return unlink($dir);
    }

    foreach (scandir($dir) as $item) {
        if ($item == '.' || $item == '..') {
            continue;
        }

        if (!deleteDirectory($dir . DIRECTORY_SEPARATOR . $item)) {
            return false;
        }

    }

    return rmdir($dir);
}

deleteDirectory($select);


?>
