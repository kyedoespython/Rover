from flask import render_template
from flask import request
from flask import session
from flask import redirect
from flask import url_for
from flask import flash
from . import auth_bp

# store passwords as hash via werkzeug
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

# regex for password requirements. validation error for err handling
from wtforms.validators import ValidationError
import re

import os
from dotenv import load_dotenv

@auth_bp.route("/Rover/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

@auth_bp.route("/Handle_signup", methods=["POST", "GET"])
def Handle_Signup():
    if request.method == "POST":
        email_ = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        phone_number = request.form.get("telephone")
        country = request.form.get("country")

    def Validation_check_password(password):
        if not re.match(r'^[A-Z]', password): raise ValidationError("Password must start with an upper case character")
        elif len(password) < 8: raise ValidationError("Password must be longer than 8 characters")
        elif not re.search(r'[!@#$%^&*]', password): raise ValidationError("Password must contain at least one special char (!@#$%^&*)")

        password_hash = generate_password_hash(password, method="scrypt:32768:16:1", salt_length=16)

@auth_bp.route("/Rover/Auth")
def Authenticate_User():
    return render_template("Auth/Auth.html")

@auth_bp.route("/HandleAuth")
def Handle_Auth():
    auth_code = request.form.get("authCode")

@auth_bp.route("/Rover/Login")
def Login():
    return render_template("Login/Login.html")

@auth_bp.route("/Handle_Login", methods=["POST", "GET"])
def Handle_Login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

@auth_bp.route("/Rover/Contact")
def Contact():
    return render_template("Contact/Contact.html")