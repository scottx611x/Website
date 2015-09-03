<head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <meta name="viewport" content="width=device-width" />
    <link href='http://fonts.googleapis.com/css?family=Raleway:200' rel='stylesheet' type='text/css'>
    <link rel="stylesheet" type="text/css" href="jquery.fullPage.css" />
        <link rel="stylesheet" type="text/css" media="all" href="Styles.css" />
    <link rel="stylesheet" type="text/css" media="all" href="Animations.css" />
    <link rel="stylesheet" href="https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css" />
    <link rel="stylesheet" type="text/css" media="all" href="transitions.css" />

</head>
<script src="http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js"></script>
<script src="https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/jquery-ui.min.js"></script>
<script type="text/javascript" src="jquery.easings.min.js"></script>
<script type="text/javascript" src="jquery.slimscroll.min.js"></script>
<script type="text/javascript" src="jquery.fullPage.js"></script>
<script type="text/javascript" src="jquery.collagePlus.min.js"></script>

<script>
$(document).ready(function() {
    $('.Collage').collagePlus(
        {
            'effect' : 'effect-5',
        }
    );
    $('#fullpage').fullpage({
        //Navigation
        menu: '#myMenu_php',
        anchors: ['firstPage', 'secondPage', 'thirdPage'],
        navigation: false,
        navigationPosition: 'left',
        slidesNavigation: true,
        slidesNavPosition: 'bottom',

        //Scrolling
        css3: true,
        scrollingSpeed: 600,
        autoScrolling: true,
        scrollBar: false,
        easing: 'easeInQuart',
        easingcss3: 'ease',
        loopBottom: true,
        loopTop: true,
        loopHorizontal: true,
        continuousVertical: false,
        normalScrollElements: '#element1, .element2',
        scrollOverflow: true,
        touchSensitivity: 50,
        normalScrollElementTouchThreshold: 5,

        //Accessibility
        keyboardScrolling: true,
        animateAnchor: true,

        //Design
        controlArrows: true,
        verticalCentered: true,
        resize: true,
        //sectionsColor: ['blue', '#4BBFC3', '#7BAABE', 'whitesmoke'],
        paddingTop: '3em',
        paddingBottom: '10px',
        //fixedElements: '#header, #footer',
        responsive: 0,

        //Custom selectors
        sectionSelector: '.section',
        slideSelector: '.slide',

        //events
        onLeave: function(index, nextIndex, direction) {},
        afterLoad: function(anchor, index) {},
        afterRender: function() {},
        afterResize: function() {},
        afterSlideLoad: function(anchorLink, index, slideAnchor, slideIndex) {},
        onSlideLeave: function(anchorLink, index, slideIndex, direction) {}
    });
});
</script>
<html>

<title>Code Examples</title>

<body>
<div class="fixed">
        <a id="Err" href="http://www.scott-ouellette.com">Home</a>
        <a id="Header_Home" href="http://www.scott-ouellette.com"><img src="Images/home.png"/></a>
        <ul id="myMenu_php">
            <li data-menuanchor="firstPage"><a class="pullUp" href="#firstPage">Coding Examples</a>
            </li>
        </ul>
    </div>
<div id="fullpage" style="text-align:center;">
<div class="section Collage effect-parent" data-anchor="firstPage">
<br>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Hydro.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/perl_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> Hydrophobic % Checker </div>
    <br><br><br>
    <a id="ScriptDL" href="Hydro_Checker.zip" download="Hydro_Checker.zip" class="ScriptDL">Download</a>
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Fuzzy.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/perl_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> Gene "Fuzzy" Finder </div>
    <br><br><br>
    <a id="ScriptDL" href="Gene_Fuzzy_Finder.zip" download="Gene_Fuzzy_Finder.zip" class="ScriptDL">Download</a>
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Scraper.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/python_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> TEST </div>
    <br><br><br>
    <!--<a id="ScriptDL" href="Resume.pdf" download="Scott_O_Resume.pdf" class="ScriptDL">Download</a>-->
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Scraper.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/python_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> TEST </div>
    <br><br><br>
    <!--<a id="ScriptDL" href="Resume.pdf" download="Scott_O_Resume.pdf" class="ScriptDL">Download</a>-->
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Scraper.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/python_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> TEST </div>
    <br><br><br>
    <!--<a id="ScriptDL" href="Resume.pdf" download="Scott_O_Resume.pdf" class="ScriptDL">Download</a>-->
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Scraper.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/python_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> TEST </div>
    <br><br><br>
    <!--<a id="ScriptDL" href="Resume.pdf" download="Scott_O_Resume.pdf" class="ScriptDL">Download</a>-->
  </div>
</div>
<div class="box"> <img src="http://www.scott-ouellette.com/Images/Scraper.png"height="200px"width="200px"/>
  <div class="overbox">
    <div class="icon overtext"><img src="http://www.scott-ouellette.com/Images/python_icon.png"/></div>
    <br><br><br><br>
    <div class="tagline overtext"> TEST </div>
    <br><br><br>
    <!--<a id="ScriptDL" href="Resume.pdf" download="Scott_O_Resume.pdf" class="ScriptDL">Download</a>-->
  </div>
</div>
<br>
</div>
</div>
</body>
</html>

