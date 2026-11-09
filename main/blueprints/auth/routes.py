from flask import render_template
from flask import request
from flask import flash
from flask import redirect
from flask import url_for
from flask_login import current_user
from flask_login import login_user
from flask_login import login_required

from flask_mail import Message
from flask import session

# store passwords as hash via werkzeug
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from . import auth_bp

# import account validator checks from user service
from main.services.user_service import Account_Exists_Validator, Contents_Checker

# import the schema for database manipulation
from main.models.user import Accounts, Authentication

# import auth services for auth code generation, storing hashed auth code, verifying auth code
from main.services.auth_service import AuthCode_check, Create_Auth_Code
from main.services.auth_service import SignupAttemptMail

from datetime import datetime, timedelta, timezone

# main / extension imports
from main.extensions import db
from main.extensions import mail
from main.extensions import limiter

# This is the signup route for the signup page
@auth_bp.route("/Rover/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

# This is the signup handling route for getting data from the signup form
@auth_bp.route("/Handle_signup", methods=["POST", "GET"])
@limiter.limit("5/minute; 50 per day")
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
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Username_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Password_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Phone_Number_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Country_Valid()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        account_checker = Account_Exists_Validator(email, username, phone_number)

        # Obfuscate / hide which field caused the duplicate (Issue 6)
        if account_checker.Email_Found() or account_checker.Username_Found() or account_checker.Phone_number_Found():
            
            # Call the service — it silently emails the existing owner (if any)
            SignupAttemptMail(email)

            # Same response as a successful signup
            flash("Check your email inbox", "info")
            session['pending_auth_email'] = email
            return redirect(url_for("auth.Authenticate_User"))

        # Convert empty string to None for phone number
        clean_empty_phone_number = phone_number if phone_number else None

        AccountBlock = Accounts(
            email=email,
            username=username,
            password=generate_password_hash(password),
            phone_number=clean_empty_phone_number,
            country_of_origin=country
        )

        db.session.add(AccountBlock)
        db.session.flush()

        success, message = Create_Auth_Code(AccountBlock)

        if success:
            flash("Account created successfully, Check your email inbox for your auth code", "success")
        else:
            flash(message, "error")

        db.session.commit()

        session['pending_auth_email'] = email
        return redirect(url_for("auth.Authenticate_User"))

@auth_bp.route("/Rover/Auth")
def Authenticate_User():
    return render_template("Auth/Auth.html")

@auth_bp.route("/HandleAuth", methods=["POST", "GET"])
@limiter.limit("10/minute; 100 per day") # limit to 10 requests per minute and max 100 requests per day
def Handle_Auth():
    if request.method == "POST":

        # get auth code with no spaces
        auth_code = request.form.get("authCode", "").strip()

        # run the AuthCode_check function in user_service
        is_valid, message = AuthCode_check(auth_code)
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Authenticate_User"))

        # Get the pending email from the session
        pending_email = session.get('pending_auth_email')
        
        if not pending_email:
            flash("No authentication session found.", "error")
            return redirect(url_for("auth.Login"))

        # Look up the user by the first instance of the users entered email
        user = Accounts.query.filter_by(email=pending_email).first()

        # if the user or authentication data is empty, present an error via flash message
        # then redirect the user back to the login page
        if not user or not user.authentication_data:
            flash("Error finding account.", "error")
            return redirect(url_for("auth.Login"))

        # check if the expiry time of the auth code exists in the database
        if not user.authentication_data.auth_code_expires:
            flash("This code is no longer valid", "error")
            return redirect(url_for("auth.Authenticate_User"))

        # compare timestamps in UTC (24 hour clock)
        expiry = user.authentication_data.auth_code_expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            flash("Your auth code has expired", "error")
            return redirect(url_for("auth.Authenticate_User"))

        # check the auth code matches the hash
        if check_password_hash(user.authentication_data.auth_code, auth_code):
            user.authentication_data.authenticated = True
            
            # Clear the code and expiry so it can't be reused
            user.authentication_data.auth_code = None
            user.authentication_data.auth_code_expires = None
            
            db.session.commit()
            
            # Clear the session
            session.pop('pending_auth_email', None)

            # redirect user who is now authenticated to the login page
            flash("Account successfully authenticated! Please log in.", "success")
            return redirect(url_for("auth.Login"))

        else:
            flash("Invalid auth code", "error")
            return redirect(url_for("auth.Authenticate_User"))

# Route for resending auth token to user email, use POST method only using csrf protection
@auth_bp.route("/Resend_Auth", methods=["POST"])
@limiter.limit("10/minute; 100 per day") # limit to 10 requests per minute and max 100 requests a day
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

    # 10 minute cooldown check for the resend auth code button
    if user.authentication_data.last_code_sent_at:
        last_sent = user.authentication_data.last_code_sent_at.replace(tzinfo=timezone.utc)
        time_passed = datetime.now(timezone.utc) - last_sent

        if time_passed < timedelta(minutes=10):
            minutes_left = 10 - int(time_passed.total_seconds() // 60)
            flash(f"You must wait {minutes_left} before you can request a new auth code", "error")
            return redirect(url_for("auth.Authenticate_User"))

    # create an auth code for the user from user_service
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
@limiter.limit("5 per minute") # 5 login request per IP address per minute, no max per day
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

        # Rate limit the users login attempts to 5 per 
        if user.failed_login_attempts >= 5 and user.last_login_attempt:
            last_attempt = user.last_login_attempt.replace(tzinfo=timezone.utc)
            time_passed = datetime.now(timezone.utc) - last_attempt

            if time_passed < timedelta(minutes=15):
                minutes_left = 15 - int(time_passed.total_seconds() // 60)
                flash(f"Too many failed attempts to login, you can try again in {minutes_left} minutes", "error")
                return redirect(url_for("auth.Login"))
            else:
                user.failed_login_attemps = 0 # if 15 minutes has passed reset the failed login attempts to 0
                user.last_login_attempt = datetime.now(timezone.utc)
                db.session.commit() # commit change

        # log the user in
        login_user(user)
        
        flash(f"Glad to have you back {user}!", "success")
        
        # take the user to the design page
        return redirect(url_for("auth.DesignDash"))

@auth_bp.route("/DesignDashboard")
@login_required # only logged in users can access the design dashboard
def DesignDash():
    return render_template("Design/DesignDash.html")