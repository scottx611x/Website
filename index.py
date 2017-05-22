import random

from flask import Flask
from flask import render_template

app = Flask(__name__)
app.debug = True

templates = ["tilt-shift", "voronoi"]


@app.route('/', methods=['GET'])
def index():
    return render_template('{}.html'.format(random.choice(templates)))
