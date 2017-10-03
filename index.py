import random

from flask import Flask
from flask import render_template

app = Flask(__name__)
app.debug = True

BACKGROUND_IMAGE = "fall.jpg"
templates = ["collision", "tilt-shift", "voronoi"]


# Route to choose a random template on a site visit
@app.route('/', methods=['GET'])
def index():
    return render_template(
        '{}.html'.format(
            random.choice(templates)
        ),
        background_image=BACKGROUND_IMAGE
    )


@app.route('/collision', methods=['GET'])
def collision():
    return render_template("collision.html", background_image=BACKGROUND_IMAGE)


@app.route('/tilt-shift', methods=['GET'])
def tiltshift():
    return render_template("tilt-shift.html", background_image=BACKGROUND_IMAGE)


@app.route('/voronoi', methods=['GET'])
def voronoi():
    return render_template("voronoi.html", background_image=BACKGROUND_IMAGE)
