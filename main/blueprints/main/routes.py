from flask import render_template

from . import main_bp

@main_bp.route("/")
def HomePage():
    return render_template("main/Home.html")

@main_bp.route("/About")
def AboutPage():
    return render_template("main/About.html")