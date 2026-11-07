from flask import render_template
from flask import request
from flask import flash
from flask import redirect
from flask import url_for
from flask_login import current_user, login_user
from flask_mail import Message
from flask import session

# store passwords as hash via werkzeug
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from . import auth_bp

# import account validator checks from user service
from main.services.user_service import Account_Exists_Validator, Contents_Checker
from main.models.user import Accounts, Authentication
from main.services.user_service import AuthCode_check, Create_Auth_Code

# auth code imports
from dotenv import load_dotenv
import os
import random
from datetime import datetime, timedelta, timezone
from main.extensions import db, mail

##
# This is the signup route for the signup page
##
@auth_bp.route("/Rover/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

##
## This is the signup handling route for getting data from the signup form
##  
@auth_bp.route("/Handle_signup", methods=["POST", "GET"])
def Handle_Signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password")
        phone_number = request.form.get("telephone", "").strip()
        country = request.form.get("country", "").strip()

        contents_checker = Contents_Checker(email, username, password, phone_number, country)

        is_valid, message = contents_checker.Check_Email_Contents()
        if not is_valid:
            print(f"DEBUG ERROR: Email - {message}") 
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Username_Contents()
        if not is_valid:
            print(f"DEBUG ERROR: Username - {message}") 
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Password_Contents()
        if not is_valid:
            print(f"DEBUG ERROR: Password - {message}") 
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Phone_Number_Contents()
        if not is_valid:
            print(f"DEBUG ERROR: Phone - {message}") 
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Country_Valid()
        if not is_valid:
            print(f"DEBUG ERROR: Country - {message}") 
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        Check_for_ = Account_Exists_Validator(email, username, phone_number)

        if Check_for_.Email_Found():
            flash("Email already exists", "error")
            return redirect(url_for("auth.Signup")) 

        if Check_for_.Username_Found():
            flash("Username in use", "error")
            return redirect(url_for("auth.Signup")) 

        if Check_for_.Phone_number_found():
            flash("Phone number already in use", "error")
            return redirect(url_for("auth.Signup")) 

        # make it store empty value as None
        clean_empty_phone_number = phone_number if phone_number else None

        # Insert the user
        AccountBlock = Accounts(
            email=email,
            username=username,
            password=generate_password_hash(password),
            phone_number=phone_number,
            country_of_origin=country
        )
        db.session.add(AccountBlock)
        db.session.flush() # retrieve user_id for auth table

        success, message = Create_Auth_Code(AccountBlock)

        if success:
            flash("Account created successfully, Check your email inbox for your auth code", "success")
        else:
            flash(message, "error")

        db.session.commit()

        # Store email in session so the Auth page knows who is verifying
        session['pending_auth_email'] = email

        return redirect(url_for("auth.Authenticate_User"))

@auth_bp.route("/Rover/Auth")
def Authenticate_User():
    return render_template("Auth/Auth.html")

@auth_bp.route("/HandleAuth", methods=["POST", "GET"])
def Handle_Auth():
    if request.method == "POST":
        auth_code = request.form.get("authCode", "").strip()

        is_valid, message = AuthCode_check(auth_code)
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Authenticate_User"))

        # Get the pending email from the session
        pending_email = session.get('pending_auth_email')
        
        if not pending_email:
            flash("No authentication session found.", "error")
            return redirect(url_for("auth.Login"))

        # Look up the user by email
        user = Accounts.query.filter_by(email=pending_email).first()

        if not user or not user.authentication_data:
            flash("Error finding account.", "error")
            return redirect(url_for("auth.Login"))

        if check_password_hash(user.authentication_data.auth_code, auth_code):
            user.authentication_data.authenticated = True
            
            # Clear the code and expiry so it can't be reused
            user.authentication_data.auth_code = None
            user.authentication_data.auth_code_expires = None
            
            db.session.commit()
            
            # Clear the session since we are done
            session.pop('pending_auth_email', None)
            
            flash("Account successfully authenticated! Please log in.", "success")
            return redirect(url_for("auth.Login"))

        else:
            flash("Invalid auth code", "error")
            return redirect(url_for("auth.Authenticate_User"))

@auth_bp.route("/Resend_Auth")
def ResendAuth():
    # Get the email from the session (set during signup or login redirect)
    pending_email = session.get('pending_auth_email')
    
    if not pending_email:
        flash("No authentication session found. Please log in again.", "error")
        return redirect(url_for("auth.Login"))

    # Find the user in the database
    user = Accounts.query.filter_by(email=pending_email).first()

    if not user:
        flash("Error finding account.", "error")
        return redirect(url_for("auth.Login"))

    # Call your reusable service function
    success, message = Create_Auth_Code(user)
    
    if success:
        flash("A new auth code has been sent to your email.", "success")
    else:
        flash(message, "error")

    # Redirect right back to the auth page
    return redirect(url_for("auth.Authenticate_User"))

@auth_bp.route("/Rover/Login")
def Login():
    return render_template("Login/Login.html")

@auth_bp.route("/Handle_Login", methods=["POST", "GET"])
def Handle_Login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Find the user in the database
        user = Accounts.query.filter_by(username=username).first()

        # Check if user exists and password is correct
        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("auth.Login"))

        # Check if they have verified their email (authenticated)
        if not user.authentication_data.authenticated:
            
            # FIX: Check if their code has expired before sending them to the auth page
            if user.authentication_data.auth_code_expires:
                expiry = user.authentication_data.auth_code_expires.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expiry:
                    flash("Your auth code expired. Please request a new one.", "error")
                    # Here you'd ideally have a route to regenerate and resend the code
                    return redirect(url_for("auth.Login"))
            
            flash("Please verify your email before logging in.", "error")

            # Save their email so the auth page knows who they are
            session['pending_auth_email'] = user.email 
            return redirect(url_for("auth.Authenticate_User"))

        # log the user in
        login_user(user)
        
        flash(f"Welcome back {user}!", "success")
        
        # take the user to the design page
        return redirect(url_for("auth.DesignDash"))

@auth_bp.route("/Rover/Contact")
def Contact():
    return render_template("Contact/Contact.html")

@auth_bp.route("/DesignDashboard")
def DesignDash():
    return render_template("Design/DesignDash.html")