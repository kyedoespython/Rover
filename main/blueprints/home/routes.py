from flask import render_template
from . import home_bp

@home_bp.route("/Rover/Home/")
def Rover_Home_Page():
    return render_template("Home/Home.html")