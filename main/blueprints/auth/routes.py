from flask import render_template
from flask import request
from flask import session
from flask import redirect
from flask import url_for
from flask import flash
from flask_login import current_user
from flask_mail import Message
from main.extensions import mail
from . import auth_bp
from main.extensions import db, mail
from main.models.user import Accounts, Authentication

# store passwords as hash via werkzeug
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

# regex for password requirements. validation error for err handling
from wtforms.validators import ValidationError
import re
import random # used for generating auth code (7 digits)
from datetime import datetime, timedelta, timezone # for timestamps

import os
from dotenv import load_dotenv

@auth_bp.route("/Rover/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

##
## This is the signup page's form data collection which uses the method 'POST' to collect the data inside the name fields in the html form
##
@auth_bp.route("/Handle_signup", methods=["POST", "GET"])
def Handle_Signup():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        phone_number = request.form.get("telephone")
        country = request.form.get("country")

    def Account_Validations(email, username, password, phone_number, country):
        Validation_check_email(email)
        Validation_check_username(username)

    def Validation_check_email(email):
        if len(email) < 0: raise ValidationError("Email must not be empty")
        elif not "@" in email: raise  ValidationError("Email address must contain an @ symbol")

    # validation of the password, username, email, phone number, country
    def Validation_check_password(email, username, password, phone_number, country):
        if not re.match(r'^[A-Z]', password): raise ValidationError("Password must start with an upper case character")
        elif len(password) < 8: raise ValidationError("Password must be longer than 8 characters")
        elif not re.search(r'[!@#$%^&*]', password): raise ValidationError("Password must contain at least one special char (!@#$%^&*)")

        Validation_check_username(username)

    def Validation_check_username(username):
        if len(username) < 4: raise ValidationError("Username must be above 4 characters")

        # generate password hash
        password_hash = generate_password_hash(password, method="scrypt:32768:16:1", salt_length=16)
        Add_User(email, username, password_hash, phone_number, country)

    def Add_User(email, username, password_hash, phone_number, country):
        # insert account 
        user_account = Accounts(email=email, username=username, password=password_hash, phone_number=phone_number, country=country)

        db.session.add(user_account)
        db.session.commit()

        return True, "Account created"


@auth_bp.route("/Rover/Auth")
def Authenticate_User():
    return render_template("Auth/Auth.html")

@auth_bp.route("/HandleAuth")
def Handle_Auth():

    def generate_auth_code():
        auth_int_ = str(random.randint(1000000, 9999999))
        hashed_auth_int_ = generate_password_hash(auth_int_)

        current_user.auth_code = hashed_auth_int_
        current_user.auth_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.session.commit()

        receiver_email = current_user.email

        msg = Message(
            subject="Rover Auth Code",
            sender="LocalRoverWeb@gmail.com",
            recipients=[receiver_email]
        )

        msg.body = f"Your Rover authentication code is : {auth_int_} \n\n You have 10 minutes to use this code"
        mail.send(msg) # send the auth code

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