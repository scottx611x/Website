import random

from flask import Flask
from flask import render_template

app = Flask(__name__)
app.debug = False
app.prior_template = None

TITLE = "Scott's Webpage"
BACKGROUND_IMAGE = "fall.jpg"

template_context = {
    "background_image": BACKGROUND_IMAGE,
    "title": TITLE
}


@app.route('/', methods=['GET'])
def index():
    random_template = get_random_template()

    while random_template == app.prior_template:
        random_template = get_random_template()

    app.prior_template = random_template
    return render_helper(random_template)


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


def get_random_template():
    template_names = ["collision", "tilt-shift", "voronoi"]
    return '{}.html'.format(random.choice(template_names))
