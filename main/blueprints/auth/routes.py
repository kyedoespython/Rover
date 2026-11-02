from flask import render_template
from . import auth_bp

@auth_bp.route("/register")
def register():
    return render_template("Register.html")

@auth_bp.route("/login")
def login():
    return render_template("Login.html")
