import random

from flask import Flask
from flask import render_template

app = Flask(__name__)
app.debug = True

templates = ["collision", "poisson-disc", "tilt-shift", "voronoi"]


# Route to choose a random template on a site visit
@app.route('/', methods=['GET'])
def index():
    return render_template(
        '{}.html'.format(
            random.choice(templates)
        )
    )


@app.route('/collision', methods=['GET'])
def collision():
    return render_template("collision.html")


@app.route('/tilt-shift', methods=['GET'])
def tiltshift():
    return render_template("tilt-shift.html")


@app.route('/poisson-disc', methods=['GET'])
def poisson_disc():
    return render_template("poisson-disc.html")


@app.route('/voronoi', methods=['GET'])
def voronoi():
    return render_template("voronoi.html")

if __name__ == "__main__":
    app.run()
