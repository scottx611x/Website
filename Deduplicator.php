<html>
<head>
    <link href='http://fonts.googleapis.com/css?family=Londrina+Sketch' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Cabin+Sketch' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Roboto:300italic' rel='stylesheet' type='text/css'>
</head>

<style>

body {
    background: #81b71a;
    margin:0;
    padding:0;
}
#Title_container{
    width:100%;
    height:150px;
    background: #262626;
    margin:0;
    padding: 0;
    top:0;
    left:0;
    -webkit-box-shadow: 0 7px 4px #1E1E1E;
    -moz-box-shadow: 0 7px 4px #1E1E1E;
    box-shadow: 0 7px 4px #1E1E1E;

}
.Title1 {
    font-size: 48px;
    font-family: 'Londrina Sketch', cursive;
    color: #ffffff;
    margin:0;
}
.Title2 {
    font-size: 48px;
    font-family: 'Londrina Sketch', cursive;
    color: #ffffff;
    margin:0;
}
#input {
    border: 5px solid  #262626;
    border-radius: 10px;
    height: 35px;
    font-size: 18px;
    font-family: 'Roboto', sans-serif;
    text-align: center;
    padding-bottom:5px;
    padding-top:5px;
}
#login {
    display: none;
  }

  #loggedin {
    display: none;
  }
#submit {
    border: 5px solid  #262626;
    border-radius: 25px;
    background: #000000;
    color: #FFFFFF;
    height: 35px;
    width: 150px;
    font-size: 18px;
    font-family: 'Roboto', sans-serif;
    text-align: center;

}
p{
    font-size: 18px;
    font-family: 'Cabin Sketch', cursive;
    color: #ffffff;
}
</style>





<body>
<div id = "Title_container" align = "center">
<br>
<br>
<p class = "Title1">SPOTIFY</p>
<p class = "Title2">Duplicate Ridder</p>
</div>
<br>
<div align = "center">
<form id='myform' action='#' method='post'>
<INPUT id = "input" TYPE = "Text" PLACEHOLDER = "Username" NAME = "username"><br><br>
<INPUT id = "input" TYPE = "Text" PLACEHOLDER = "Password" NAME = "password"><br><br>
<INPUT id = "input" TYPE = "Text" PLACEHOLDER = "Spotify Playlist URI" NAME = "playlist"><br><br>
<input id = "submit" id='Submit' type='submit' name='submit' value='Submit' /><br>
</form>
</div>
<div id="login">
     <h1>First, log in to spotify</h1>
     <a href="/login">Log in</a>
    </div>
    <div id="loggedin">
    </div>
 </div>

 <script id="loggedin-template" type="text/x-handlebars-template">
    <h1>Logged in as {{display_name}}</h1>
    <img id="avatar" width="200" src="{{images.0.url}}" />
    <dl>
     <dt>Display name</dt><dd>{{display_name}}</dd>
     <dt>Username</dt><dd>{{id}}</dd>
     <dt>Email</dt><dd>{{email}}</dd>
     <dt>Spotify URI</dt><dd><a href="{{external_urls.spotify}}">{{external_urls.spotify}}</a></dd>
     <dt>Link</dt><dd><a href="{{href}}">{{href}}</a></dd>
     <dt>Profile Image</dt><dd>{{images.0.url}}</dd>
    </dl>
    <p><a href="/">Log in again</a></p>
 </script>
<?php
if(isset($_POST['submit'])){
$USERNAME = $_POST['username'];
$PASSWORD = $_POST['password'];
$PLAYLIST = $_POST['playlist'];

#$cmda = "echo Hockey15! | sudo -S python pyspotify_test.py 2>&1";
$cmda = "echo Hockey15! | sudo -S python pyspotify_test.py" . " " . $USERNAME . " " . $PASSWORD . " " . $PLAYLIST . " 2>&1";
exec($cmda,$outputb);
foreach ($outputb as $valueb)
    echo $valueb;
$f1 = file_get_contents("PLAYLIST",FILE_USE_INCLUDE_PATH);
echo("<div align = 'center'><br>$f1<br></div>");
}
?>
</body>
</html>