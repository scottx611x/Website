<head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <meta name="viewport" content="width=device-width" />
    <link href='http://fonts.googleapis.com/css?family=Raleway:300' rel='stylesheet' type='text/css'>
    <link rel="stylesheet" type="text/css" href="jquery.fullPage.css" />
    <link rel="stylesheet" type="text/css" media="all" href="Animations.css" />
    <link rel="stylesheet" type="text/css" media="all" href="Styles.css" />
    <link rel="stylesheet" href="https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css" />
    <link rel="stylesheet" type="text/css" media="all" href="transitions.css" />
    <link rel="stylesheet" type="text/css" href="theme_site.css">
    <link rel="stylesheet" type="text/css" href="ihover.min.css">
    <link rel="stylesheet" href="idd-zoom.css">


    <!---<script type="text/javascript">
        window.onload = pre_loader;
        function pre_loader() {
            document.getElementById('Blog').innerHTML = '<iframe id="Blog_Content" data-src="http://scottx611x.tumblr.com/" frameborder="0"></iframe>';
        }
    </script>-->
    <script type="text/javascript">
            ! function(d, s, id) {
                var js, fjs = d.getElementsByTagName(s)[0],
                    p = /^http:/.test(d.location) ? 'http' : 'https';
                if (!d.getElementById(id)) {
                    js = d.createElement(s);
                    js.id = id;
                    js.src = p + '://platform.twitter.com/widgets.js';
                    fjs.parentNode.insertBefore(js, fjs);
                }
            }(document, 'script', 'twitter-wjs');
            </script>
</head>

<html>
<title>Scott's Webpage</title>

<body>
    <div class="fixed">
        <ul id="myMenu">
            <li data-menuanchor="firstPage" class="pulse activeslide"><a class="pullUp" href="#firstPage">Home</a>
            </li>
            <li data-menuanchor="secondPage"><a class="pullUp" href="#secondPage">Resume</a>
            </li>
            <li data-menuanchor="thirdPage"><a class="pullUp" href="#thirdPage">Contact</a>
            </li>
            <li data-menuanchor="fourthPage"><a class="pullUp" href="#fourthPage">Projects</a>
            </li>
            <li data-menuanchor="fifthPage"><a class="pullUp" href="#fifthPage">Blog</a>
            </li>
        </ul>
    </div>
    <div id="fullpage" style="text-align:center;">
        <div class="section" id="MoiContainer" data-anchor="firstPage">
            <!--<img id="Moi" class="fadeIn" src="Images/PlaceHolder.png" />-->
            <br>
            <br>
            <div class="ih-item circle colored effect19">
                <a href="#">
                    <div class="img"><img src="new.png" alt="img"></div>
                    <div class="info">
                        <h3>Scott <br> Ouellette</h3>
                        <p>Computer Scientist and Web Developer</p>
                    </div>
                </a>

            </div>
            
            <div id="Moi2">
                <a href="https://github.com/scottx611x">
                    <img id="GITHUB" src="Images/Github.png" />
                </a>
                <a href="http://www.linkedin.com/pub/scott-ouellette/69/2b/209/">
                    <img id="LINKEDIN" src="Images/Linkedin.png" />
                </a>
                <a href="https://twitter.com/Scott_Ouellette">
                    <img id="TWITTER" src="Images/Twitter.png" />
                </a>
                <a href="https://www.facebook.com/scott.ouellette1">
                    <img id="FACEBOOK" src="Images/fb.png" />
                </a>
                <a href="http://instagram.com/scottylago11">
                    <img id="INSTAGRAM" src="Images/Instagram.png" />
                </a>
            </div>
            <br>
            
            <div id="Moi3">
                <a id="Twitter" href="https://twitter.com/Scott_Ouellette" class="twitter-follow-button" data-show-count="false">Follow @Scott_Ouellette</a>
            </div>
            <br>
            <br>
        </div>
        <div class="section" data-anchor="secondPage">
            <br>
            <br>
            <div id="Res" class="">
                <img id="Resume" src="Images/Resume.png" />
            </div>
            <br>
            <a id="Resume1" href="Resume.pdf" download="Scott_O_Resume.pdf" class="Res_Dl">Download</a>
        </div>
        <div class="section" id="Contact_wrapper" data-anchor="thirdPage">
            <div id="Contact_top" align="center" class="">
                <p>Contact Info</p>
            </div>
            <div id="Contact_mid" class="">
                <a href="https://github.com/scottx611x">
                    <img id="GITHUB" src="Images/Github.png" />
                </a>
                <a href="http://www.linkedin.com/pub/scott-ouellette/69/2b/209/">
                    <img id="LINKEDIN" src="Images/Linkedin.png" />
                </a>
                <a href="https://twitter.com/Scott_Ouellette">
                    <img id="TWITTER" src="Images/Twitter.png" />
                </a>
                <a href="https://www.facebook.com/scott.ouellette1">
                    <img id="FACEBOOK" src="Images/fb.png" />
                </a>
                <a href="http://instagram.com/scottylago11">
                    <img id="INSTAGRAM" src="Images/Instagram.png" />
                </a>
            </div>
            <div id="wrapper" align="center">
                <br>
                <br>
                <br>
                <div id="Contact1"><img class="mail_icon" src="email.png" height="35px" width="50px" />
                    <br>
                    <br>
                    <a href="mailto:ouellettes1@wit.edu? Subject=Hello Scott" target="_top" class="Email1" title="Click to Email">ouellettes1@wit.edu</a>
                    <br>
                    <br>
                </div>
                <div id="Contact2"><img class="mail_icon" src="email.png" height="35px" width="50px" />
                    <br>
                    <br>
                    <a href="mailto:scottx611x@gmail.com? Subject=Hello Scott" target="_top" class="Email2" title="Click to Email">scottx611x@gmail.com</a>
                    <br>
                    <br>
                </div>
                <br>
            </div>
            <!--<br><br><br><br><br>
            <script src="http://coinwidget.com/widget/coin.js"></script>
            <div id="BTC" class="">
                <script>
                CoinWidgetCom.go({
                    wallet_address: "1JjDrPVDAAavzbRNSW935e4r4hufEWkRy1",
                    currency: "bitcoin",
                    counter: "hide",
                    alignment: "bc",
                    qrcode: true,
                    auto_show: false,
                    lbl_button: "Donate!",
                    lbl_address: "My Bitcoin Address:",
                    lbl_count: "transactions",
                    lbl_amount: "BTC"
                });
                </script>
            </div>-->
        </div>
        <!--<div class="section Collage effect-parent"data-anchor="fourthPage"><br><br><br>
            <div class="box"><img src="http://www.scott-ouellette.com/Images/Final.png" /><div class="overbox"><div class="icon overtext"><br><br><img src="http://www.scott-ouellette.com/Images/www.png"height="35px"width="35px"/></div><div class="tagline overtext">Hydrophobic % Checker GUI</div><br><br><br><br><a href="http://www.scott-ouellette.com/Hydro_Check.php" class="ScriptDL">View</a></div></div><div class="box"><img src="http://www.scott-ouellette.com/Images/perl.png"/><div class="overbox"><div class="icon overtext"><br><br><img src="http://www.scott-ouellette.com/Images/perl_icon.png"height="35px"width="35px"/></div><div class="tagline overtext">Hydrophobic % Checker</div><br><br><br><br><a href="Hydro_Checker.zip"download="Hydro_Checker.zip"class="ScriptDL">Download</a></div></div><div class="box"><img src="http://www.scott-ouellette.com/Images/perl.png"/><div class="overbox"><div class="icon overtext"><br><br><img src="http://www.scott-ouellette.com/Images/perl_icon.png"height="35px"width="35px"/></div><div class="tagline overtext">Gene "Fuzzy" Finder</div><br><br><br><br><a href="Gene_Fuzzy_Finder.zip"download="Gene_Fuzzy_Finder.zip"class="ScriptDL">Download</a></div></div><br><br><br></div>-->
        <div class="section" data-anchor="fourthPage">
            
            <div id="P3" class="slide" data-anchor="slide0">
                <h1>Hydrophobic % Checker Site</h1> 
                <div id="P3_over">
                <br>
                    <a href="http://www.scott-ouellette.com/Hydro_Check.php" class="SiteView">View Site</a>
                    <br><br><br>
                    <img src="Images/www.png" height="40" width="40" />
                    <h2>Website that can determine the most hydrophobic proteins of any Bacteria from NCBI's database.</h2>
                </div>
                <img id="P3_plus" class="pulse" src="Images/plus_dark.png" height="50" width="50" />
                <br><br>
                <div id="P3_under">                    
                    <script src="https://gist.github.com/scottx611x/ab15249f1788b2ecaae5.js"></script>
                </div>
                <br><br><br><br><br><br>
            </div>
            <div id="P1" class="slide" data-anchor="slide1">
                <h1>Brainf**k Interpreter</h1>
                <div id="P1_over">
                    <img src="Images/python_icon.png" height="40" width="40" />
                    <h2>Semi-optimized interpreter for the esoteric programming language: Brainf**k.</h2>
                </div>
                <img id="P1_plus" class="pulse" src="Images/plus_dark.png" height="50" width="50" />
                <br><br>
                <div id="P1_under">
                    <script src="https://gist.github.com/scottx611x/efba0aafb189db8d88aa.js"></script>
                </div>
                <br><br><br><br>
            </div>
            <div id="P2" class="slide" data-anchor="slide2">
                <h1>"Lossy" Text Compression</h1>
                <div id="P2_over">
                    <img src="Images/python_icon.png" height="40" width="40" />
                    <h2>Pseudo text compression achieved through querying a thesaurus for the shorest given synonyms of each word.</h2>
                </div>
                <img id="P2_plus" class="pulse" src="Images/plus_dark.png" height="50" width="50" />
                <br><br>
                <div id="P2_under">
                    <script src="https://gist.github.com/scottx611x/bcc0d7366ea59f69dcec.js"></script>
                </div>
                <br><br><br><br>
            </div>
            <div id="P4" class="slide" data-anchor="slide3">
                <h1>Hydrophobic % Checker Script</h1>
                <div id="P4_over">
                    <img src="Images/python_icon.png" height="40" width="40" />
                    <h2>Python file that does all of the grunt work for the Hydrophobic % Checker site.</h2>
                </div>
                <img id="P4_plus" class="pulse" src="Images/plus_dark.png" height="50" width="50" />
                <br><br>
                <div id="P4_under">
                    <script src="https://gist.github.com/scottx611x/ccbde234ff380d9c0317.js"></script>
                </div>
                <br><br><br><br>
            </div>
            <div id="P5" class="slide" data-anchor="slide4">
                <h1>Gene "Fuzzy" finder</h1>
                <div id="P5_over">
                    <img src="Images/perl_icon.png" height="40" width="40" />
                    <h2>Script that determines many different characteristics of DNA sequences from a given .fna file.</h2>
                </div>
                <img id="P5_plus" class="pulse" src="Images/plus_dark.png" height="50" width="50" />
                <br><br>
                <div id="P5_under">
                    <script src="https://gist.github.com/scottx611x/784c7a64f3729cff7032.js"></script>
                </div>
                <br><br><br><br>
            </div>
        </div>
        <div class="section" data-anchor="fifthPage">
            <br><br><br>
            <div id="Blog"><iframe id="Blog_Content" src="http://scottx611x.tumblr.com/" frameborder="0"></iframe></div> 
        </div>
    </div>
    <script type="text/javascript" src="jquery-1.11.3.min.js"></script>
<script type="text/javascript" async src="idd-zoom.js"></script>
<script type="text/javascript" async src="jquery-ui.min.js"></script>
<script type="text/javascript" async src="jquery.easings.min.js"></script>
<script type="text/javascript" async src="jquery.slimscroll.min.js"></script>
<script type="text/javascript" src="jquery.fullPage.js"></script>
<script type="text/javascript" async src="pace.min.js"></script>



<script>
$(document).ready(function() {
    $('#P1_under').hide();
    $('#P2_under').hide();
    $('#P3_under').hide();
    $('#P4_under').hide();
    $('#P5_under').hide();
    $('#fullpage').fullpage({
        //Navigation
        menu: '#myMenu',
        anchors: ['firstPage', 'secondPage', 'thirdPage', 'fourthPage', 'fifthPage'],
        navigation: false,
        navigationPosition: 'left',
        slidesNavigation: false,
        slidesNavPosition: 'top',

        //Scrolling
        css3: true,
        scrollingSpeed: 500,
        autoScrolling: true,
        scrollBar: false,
        easing: 'easeInQuart',
        easingcss3: 'ease',
        loopBottom: false,
        loopTop: false,
        loopHorizontal: true,
        continuousVertical: false,
        normalScrollElements: '#element1, .element2',
        scrollOverflow: true,
        touchSensitivity: 10,
        normalScrollElementTouchThreshold: 5,

        //Accessibility
        keyboardScrolling: true,
        animateAnchor: false,

        //Design
        controlArrows: true,
        verticalCentered: true,
        resize: true,
        //sectionsColor: ['blue', '#4BBFC3', '#7BAABE', 'whitesmoke'],
        paddingTop: '3em',
        paddingBottom: '10px',
        //fixedElements: '#header, #footer',
        responsive: 0,
        touchSensitivity: 10,

        //Custom selectors
        sectionSelector: '.section',
        slideSelector: '.slide',

        //events
        onLeave: function(index, nextIndex, direction) {},
        afterLoad: function(anchor, index) {
            var activeItem1;
            var activeItem2;
            var activeItem3;
            var activeItem4;
            var activeItem5;
            var activeItem6;
            if (index == 1) {
                activeItem1 = $('#myMenu').find('li').first()
                    //activeItem2 = $('#Moi')
                    //activeItem3 = $('#Moi2')
                    //activeItem4 = $('#Moi3')
                    //activeItem5 = $('')
                    //activeItem6 = $('')
            } else if (index == 2) {
                activeItem1 = $('#myMenu').find('li:nth-child(2)')
                    //activeItem2 = $('')
                    //activeItem3 = $('#Res')
                    //activeItem4 = $('#Resume1')
                    //activeItem5 = $('')
                    //activeItem6 = $('')
            } else if (index == 3) {
                activeItem1 = $('#myMenu').find('li:nth-child(3)')
                    //activeItem2 = $('')
                    //activeItem3 = $('#Contact_mid')
                    //activeItem4 = $('#wrapper')
                    //activeItem5 = $('#BTC')
                    //activeItem6 = $('#Contact_top')
            } else if (index == 4) {
                activeItem1 = $('#myMenu').find('li:nth-child(4)')
            } else if (index == 5) {
                activeItem1 = $('#myMenu').find("li").last()
            }

            activeItem1
                .addClass('pulse activeslide')
                .siblings().removeClass('pulse activeslide');
        },
        afterRender: function() {},
        afterResize: function() {},
        afterSlideLoad: function(anchorLink, index, slideAnchor, slideIndex) {},
        onSlideLeave: function(anchorLink, index, slideIndex, direction) {}
    });

    $("#P1_plus").click(function() {
        $('#P1_over').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
        $('#P1_under').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
    });
    $("#P2_plus").click(function() {
        $('#P2_over').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
        $('#P2_under').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
    });
    $("#P3_plus").click(function() {
        $('#P3_over').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
        $('#P3_under').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
    });
    $("#P4_plus").click(function() {
        $('#P4_over').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
        $('#P4_under').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
    });
    $("#P5_plus").click(function() {
        $('#P5_over').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
        $('#P5_under').slideToggle('5000', "easeInQuart", function() {
            // Animation complete.
        });
    });
    /*
        $("#P1").hover(function(){
    $( '#P1_plus' ).attr("src","Images/plus.png");
    }, function() {
        $( '#P1_plus' ).attr("src","Images/plus_dark.png");
    });
        $("#P2").hover(function(){
    $( '#P2_plus' ).attr("src","Images/plus.png");
    }, function() {
        $( '#P2_plus' ).attr("src","Images/plus_dark.png");
    });
        $("#P3").hover(function(){
    $( '#P3_plus' ).attr("src","Images/plus.png");
    }, function() {
        $( '#P3_plus' ).attr("src","Images/plus_dark.png");
    });
        $("#P4").hover(function(){
    $( '#P4_plus' ).attr("src","Images/plus.png");
    }, function() {
        $( '#P4_plus' ).attr("src","Images/plus_dark.png");
    });
        $("#P5").hover(function(){
    $( '#P5_plus' ).attr("src","Images/plus.png");
    }, function() {
        $( '#P5_plus' ).attr("src","Images/plus_dark.png");
    });
    

    //var myScroll = new IScroll('#gists');

*/
setTimeout(function() {
        // Show our element, then call our callback
        $("#Blog").show(function() {
            // Find the iframes within our newly-visible element
            $(this).find("iframe").prop("src", function() {
                // Set their src attribute to the value of data-src
                return $(this).data("src");
            });
        });
    }, 3000);

if ( $(window).width() > 739) {     
  //Add your javascript for large screens here
  var mp = new magpic('.idd-zoom', {
    magnifierImage: 'Images/Resume-Big.png', 
    magnifierSize: 300, 
    fadeDuration: 200, 
    enabled: true, 
    initialPosition: [150,300]
});
}


});
</script>
</body>

</html>
