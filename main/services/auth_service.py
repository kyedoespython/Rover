from html import escape
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


def SendVerificationConfirmationEmail(user_account):
    username = user_account.username
    safe_username = escape(username)

    msg = Message(
        subject="Your Rover account is verified",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[user_account.email],
    )
    msg.body = (
        f"Congratulations {username}!\n\n"
        "Your Rover account has been successfully verified. "
        "You can now log in and start using Rover.\n\n"
        "Thanks for joining us,\n"
        "The Rover Team"
    )
    msg.html = f"""\
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Your Rover account is verified</title>
</head>
<body style="margin:0;padding:0;background-color:#f2f2f2;font-family:Arial,Helvetica,sans-serif;color:#202124;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f2f2f2;padding:32px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                    <tr>
                        <td style="padding:28px 32px;background-color:#111111;color:#ffffff;">
                            <p style="margin:0;font-size:13px;letter-spacing:2px;text-transform:uppercase;">Rover</p>
                            <h1 style="margin:12px 0 0;font-size:24px;line-height:1.3;">Account verified</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 16px;font-size:17px;line-height:1.6;">Congratulations <strong>{safe_username}</strong>!</p>
                            <p style="margin:0 0 24px;font-size:15px;line-height:1.7;color:#4b5563;">
                                Your Rover account has been successfully verified. You can now log in and start using Rover.
                            </p>
                            <p style="margin:0;font-size:15px;line-height:1.7;color:#4b5563;">
                                Thanks for joining us,<br><strong style="color:#202124;">The Rover Team</strong>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px;line-height:1.5;">
                            This message confirms a change to your Rover account.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    try:
        mail.send(msg)
    except Exception:
        current_app.logger.exception(
            "Failed to send verification confirmation email to %s",
            user_account.email,
        )
        return False, "Your account is verified, but the confirmation email could not be sent."

    return True, "Your account is verified. A confirmation email has been sent."


# check if the auth code field from the web page is a valid input
def AuthCode_check(auth_code):
    if not auth_code:
        return False, "auth code cannot hold an empty value"
    
    if not auth_code.isdigit():
        return False, "auth code must be a whole 7 digit number"

    if not len(auth_code) == 7:
        return False, "auth code must be 7 digits long"

    return True, "Valid code"