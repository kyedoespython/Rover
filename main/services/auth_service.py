from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
from main.extensions import db, mail
from flask_mail import Message
from flask import current_app
from main.models.user import Accounts, Authentication
import secrets

# This function is a reusable signup attempt checker
# It works by querying the database for the current sessions email address looking for the first instance
# It then checks if the user var is false meaning no user with that email exists
# If the email exists it passes in the email to the flask_mail object and sends the user an email
def SignupAttemptMail(email):
    user = Accounts.query.filter_by(email=email).first()

    if not user:
        return

    try:
        msg = Message(
        subject="Rover signup attempt",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[user.email],
        )

        msg.body = (
        f"Hello {user.username},\n\n"
        "Someone just tried to create a Rover account with this email address. "
        "If this was you, log in instead, if not ignore this message. "
        "\nRover - Support"
        )

        mail.send(msg)

    except Exception as e:
        print(f"Failed to send duplicate email notification: {e}")



# Create the auth code via secrets
def Create_Auth_Code(user_account):

    # if the user has no authenctication data, make sure they do by commiting
    if not user_account.authentication_data:
        auth_row = Authentication(user_id=user_account.user_id)
        db.session.add(auth_row)
        db.session.commit()
    
    else:
        auth_row = user_account.authentication_data

    auth_code_ = str(secrets.randbelow(9000000) + 1000000) # generate an auth code 7 digits long via randint

    auth_row.auth_code = generate_password_hash(auth_code_) # generate a hash for the auth code via werkzeug
    auth_row.auth_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10) # save the 10 minutes time to the database to ensure limit is 10 minutes
    auth_row.last_code_sent_at = datetime.now(timezone.utc) # save the copy of the timestamp showing when the last authentication attempt was
    db.session.commit()

    # call this func to send the auth code via flask mail to the users email address
    return SendAuthCode_EMAIL(user_account, auth_code_) # return / send values into the function call to be used to send the email with the auth code inside of it

# send the auth code in an email message, 
def SendAuthCode_EMAIL(user_account, auth_code_):
    try:
        msg = Message(
            subject="Rover Auth Code", 
            sender=current_app.config['MAIL_USERNAME'], # Best practice to use config
            recipients=[user_account.email]
        )

        msg.body = f"Welcome to Rover {user_account.username}!\n\nYour auth code is: {auth_code_}\n\nThis code expires in 10 minutes"
        mail.send(msg)

        return True, "Auth code sent to your email."
    
    except Exception as e:
        return False, "Failed to send email."

# check if the auth code field from the web page is a valid input
def AuthCode_check(auth_code):
    if not auth_code:
        return False, "auth code cannot hold an empty value"
    
    if not auth_code.isdigit():
        return False, "auth code must be a whole 7 digit number"

    if not len(auth_code) == 7:
        return False, "auth code must be 7 digits long"

    return True, "Valid code"