<html>
<head>
    <link href='http://fonts.googleapis.com/css?family=Londrina+Sketch' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Cabin+Sketch' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Roboto:300italic' rel='stylesheet' type='text/css'>
    <link rel="stylesheet" href="//netdna.bootstrapcdn.com/bootstrap/3.1.1/css/bootstrap.min.css">

<title>Duplicate Ridder</title>
</head>

<style>

body {
    background: #81b71a;
    margin:0;
    padding:0;
}
#Title_container{
    width:100%;
    height:200px;
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
#login, #loggedin, #user-playlist {
display: none;
}
#loggedin {
padding: 25px;
background: #D4D4D4;
border: 5px solid  #262626;
border-radius: 25px;
font-size: 18px;
font-family: 'Roboto', sans-serif;
}
#login-button{
    height:100px;
    width:250px;
    background: #016FB9;
    font-size: 24px;
    font-family: 'Roboto', sans-serif;
    margin: auto;
    position: absolute;
    -webkit-box-shadow: 0 4px 4px #003459;
    -moz-box-shadow: 0 4px 4px #003459;
    box-shadow: 0 4px 4px #003459;
    top: 0; left: 0; bottom: 0; right: 0;
}
#login-button:hover{
    -webkit-box-shadow: 0 7px 7px #003459;
    -moz-box-shadow: 0 7px 7px #003459;
    box-shadow: 0 7px 7px #003459;
}
.media-object{
    border: 5px solid #262626;
    border-radius:100px;
}
#playlist0{
    background:red;
}
#playlist1{
    background:blue;
}
#playlist2{
    background:green;
}
#user-playlist{
padding: 25px;
background: #D4D4D4;
border: 5px solid  #262626;
border-radius: 25px;
font-size: 18px;
font-family: 'Roboto', sans-serif;
}
.text-overflow {
overflow: hidden;
text-overflow: ellipsis;
white-space: nowrap;
width: 500px;
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
    <div class="container" align = "center">
    <div id="login">
        <button id="login-button" class="btn btn-primary">Log in with Spotify</button>
    </div>
    <div id="loggedin">
        <div id="user-profile">
    </div>
     </div>
     <br>
     <br>
    <div id = "user-playlist">
    </div>

    </div>

    <script id="user-profile-template" type="text/x-handlebars-template">
      <h1>Logged in as {{display_name}}</h1>
      <div class="media">
        <div class="pull-left">
          <img class="media-object" width="150" src="{{images.0.url}}" />
        </div>
        <div class="media-body">
          <dl class="dl-horizontal">
            <dt>Display name</dt><dd class="clearfix">{{display_name}}</dd>
            <dt>Id</dt><dd>{{id}}</dd>
            <dt>Email</dt><dd>{{email}}</dd>
            <dt>Spotify URI</dt><dd><a href="{{external_urls.spotify}}">{{external_urls.spotify}}</a></dd>
            <dt>Link</dt><dd><a href="{{href}}">{{href}}</a></dd>
            <dt>Profile Image</dt><dd class="clearfix"><a href="{{images.0.url}}">{{images.0.url}}</a></dd>
            <dt>Country</dt><dd>{{country}}</dd>
          </dl>
        </div>
      </div>
    </script>


    <script src="//cdnjs.cloudflare.com/ajax/libs/handlebars.js/2.0.0-alpha.1/handlebars.min.js"></script>
    <script src="http://code.jquery.com/jquery-1.10.1.min.js"></script>
    <script>
      (function() {

        var stateKey = 'spotify_auth_state';
        function getHashParams() {
          var hashParams = {};
          var e, r = /([^&;=]+)=?([^&;]*)/g,
              q = window.location.hash.substring(1);
          while ( e = r.exec(q)) {
             hashParams[e[1]] = decodeURIComponent(e[2]);
          }
          return hashParams;
        }

        function generateRandomString(length) {
          var text = '';
          var possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

          for (var i = 0; i < length; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
          }
          return text;
        };
            var userProfileSource = document.getElementById('user-profile-template').innerHTML,
            userProfileTemplate = Handlebars.compile(userProfileSource),
            userProfilePlaceholder = document.getElementById('user-profile');

        var params = getHashParams();

        var access_token = params.access_token,
            state = params.state,
            storedState = localStorage.getItem(stateKey);

        var user_id;

        if (access_token && (state == null || state !== storedState)) {
          alert('There was an error during the authentication');
        } else {
          localStorage.removeItem(stateKey);
          
          if (access_token) {
            
            $.ajax({
                url: 'https://api.spotify.com/v1/me',
                async:false,
                headers: {
                  'Authorization': 'Bearer ' + access_token
                },
                success: function(response) {
                  userProfilePlaceholder.innerHTML = userProfileTemplate(response);
                  user_id = JSON.parse(response.id).toString();
                  $('#login').hide();
                  $('#loggedin').show();
                  $('#user-playlist').show();
                  

                }});

            }else {
              $('#login').show();
              $('#loggedin').hide();
          }
        
        
        
          document.getElementById('login-button').addEventListener('click', function() {

            var client_id = '46f8c0e7e3bc47ec8b29c5c0ffd216b4'; // Your client id
            var redirect_uri = 'http://www.scott-ouellette.com/Deduplicator/Deduplicator.php'; // Your redirect uri

            var state = generateRandomString(16);

            localStorage.setItem(stateKey, state);
            var scope = 'user-read-private user-read-email';

            var url = 'https://accounts.spotify.com/authorize';
            url += '?response_type=token';
            url += '&show_dialog=true';
            url += '&client_id=' + encodeURIComponent(client_id);
            url += '&scope=' + encodeURIComponent(scope);
            url += '&redirect_uri=' + encodeURIComponent(redirect_uri);
            url += '&state=' + encodeURIComponent(state);

            window.location = url;
          }, false);

        }
      }());
     
    
    </script>
    <?php
    $user_id = $_GET['USER_ID'];
    $access_token = $_GET['ACCESS_TOKEN'];
    echo($user_id);
    echo("<br>");
    echo($access_token);
    echo("<br>");
    $output = shell_exec('python /var/www/html/Deduplicator/pyspotify.py ' . $user_id . ' ' . $access_token);
    echo($output);
    ?>
    
    <br>
    <br>

</body>
</html>