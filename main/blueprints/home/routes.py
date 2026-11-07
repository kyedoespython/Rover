from flask import render_template
from flask import url_for
from flask import redirect
from flask_login import login_required

from . import home_bp

@home_bp.route("/")
def Rover_Home_Page():
    return render_template("Home/Home.html")