from flask import render_template
from flask import url_for
from flask import redirect

from . import home_bp

@home_bp.route("/Rover/Home/")
def Rover_Home_Page():
    return render_template("Home/Home.html")