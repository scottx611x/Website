<html>
<head>
<title>HYDRO CHECKER</title>
<link rel = "stylesheet" type = "text/css" href = "styles.css">
<script src="jquery-1.11.2.min.js"></script>
</head>

<body>

<?php


exec("perl parser.pl", $output);

echo "</br>";
echo "<div align='center'>";
echo "<form action='#' method='post'>";
echo "<a id = 'Title' href='index.html'>Hydrophobic % Finder</a>";
#echo "<p id = 'TitleSub'>Scott Ouellette Comp 601</p>";
echo "<p id = 'Chooser'>Select a Bacteria from NCBI</p>";
echo "<span class='custom-dropdown custom-dropdown--emerald'>";
echo "<select class='custom-dropdown__select custom-dropdown__select--emerald' name='BactForm[]'>";
echo "<option value=''>Select...</option>";
foreach ($output as $value)
	echo "<option value=$value>$value</option>";
echo "</select>";
echo "</span>";
echo "</br>";
echo "</br>";
echo "<input id='Submit' type='submit' name='submit' value='Submit' />";
echo "</form>";
echo "</div>";
echo "</br>";

if(isset($_POST['submit'])){
foreach ($_POST['BactForm'] as $select)
{
echo "<div align = 'center'><p id='Message'>You have selected > " . $select . "</p></div>"; // Displaying Selected Value

$cmd = "python wget_dl.py " . $select;
exec($cmd,$outputa);
foreach ($outputa as $valuea)
	echo $valuea;

#$cmda = "python test.py " . $select . " 2>&1";
$cmda = "python test.py " . $select;
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
echo "<script>";
echo "$('#clicky').click(function() {";
echo "$('.DNA').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky1' type='submit' class = 'Button' value='Show Ptt Ranges'></input></div>";
echo "<script>";
echo "$('#clicky1').click(function() {";
echo "$('.Ranges').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky2' type='submit' class = 'Button' value='Show +/-'></input></div>";
echo "<script>";
echo "$('#clicky2').click(function() {";
echo "$('.PLUSMINUS').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky3' type='submit' class = 'Button' value='Show Gene Lengths'></input></div>";
echo "<script>";
echo "$('#clicky3').click(function() {";
echo "$('.Lengths').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky4' type='submit' class = 'Button' value='Show Genes'></input></div>";
echo "<script>";
echo "$('#clicky4').click(function() {";
echo "$('.Genes').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky5' type='submit' class = 'Button' value='Show Minus Strands'></input></div>";
echo "<script>";
echo "$('#clicky5').click(function() {";
echo "$('.MINUSSTRANDS').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky6' type='submit' class = 'Button' value='Show Proteins'></input></div>";
echo "<script>";
echo "$('#clicky6').click(function() {";
echo "$('.PROTEINS').toggleClass('hide_this')";
echo"})";
echo "</script>";

echo "<div class = 'REKT'><input id='clicky7' type='submit' class = 'Button' value='Show Sorted Hash'></input></div>";
echo "<script>";
echo "$('#clicky7').click(function() {";
echo "$('.HASH').toggleClass('hide_this')";
echo"})";
echo "</script>";

#echo("<div align = 'center'><br><br><img id = 'IMAGE' src='p_Hydro.png'><br></div>");
#echo("<div align = 'center' ><br><br><a class = 'LINKER' href = 'https://plot.ly/~scottx611x1c74/10/' style=\"color:white;\">Link to interactive graph</a></div>");
echo "<br>";
echo "<br>";
echo "<div id = 'IMAGE'><a href='https://plot.ly/~scottx611x1c74/10/' target='_blank' title='Top Hydrophobic Proteins ' . $select . ' style='display: block; text-align: center;'><img src='https://plot.ly/~scottx611x1c74/10.png' alt='Top Hydrophobic Proteins  ' . $select . ' style='max-width: 100%;'  onerror='this.onerror=null;this.src='https://plot.ly/404.png';' /></a><script data-plotly='scottx611x1c74:10' src='https://plot.ly/embed.js' async></script></div>";
echo "<br>";




}
}
?>
</div>

<br>
<br><br>
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

</body>
<div align="center">
<footer style="color:white;">Scott Ouellette ©2015 all rights reserved <a href = "index.html" style="color:white;"> www.scott-ouellette.com</a></footer>
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
