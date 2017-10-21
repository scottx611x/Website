import random

from flask import Flask
from flask import render_template

app = Flask(__name__)
app.debug = False

TITLE = "Scott's Webpage"
BACKGROUND_IMAGE = "fall.jpg"
template_names = ["collision", "tilt-shift", "voronoi"]

template_context = {
    "background_image": BACKGROUND_IMAGE,
    "title": TITLE
}


@app.route('/', methods=['GET'])
def index():
    return render_helper(
        '{}.html'.format(random.choice(template_names))
    )


@app.route('/collision', methods=['GET'])
def collision():
    return render_helper("collision.html")


@app.route('/tilt-shift', methods=['GET'])
def tiltshift():
    return render_helper("tilt-shift.html")


@app.route('/voronoi', methods=['GET'])
def voronoi():
    return render_helper("voronoi.html")


def render_helper(template_name):
    return render_template(template_name, **template_context)
