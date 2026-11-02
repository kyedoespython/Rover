from flask import render_template
from . import auth_bp

@auth_bp.route("/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

@auth_bp.route("/Login")
def Login():
    return render_template("Login/Login.html")

@auth_bp.route("/Contact")
def Contact():
    return render_template("Contact/Contact.html")